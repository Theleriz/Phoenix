"""Parameter-shared Transformer encoder, re-implemented from LIMU-BERT.

Upstream ``models.py`` (https://github.com/dapowan/LIMU-BERT-Public, MIT).
Only the encoder path is reproduced -- the pre-training decoder and masking
are not needed for representation extraction. Module/parameter names mirror
upstream so a pretrained checkpoint's ``transformer.*`` weights load directly.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as func

from .config import LimuBertConfig


def _split_last(x: torch.Tensor, shape: tuple[int, ...]) -> torch.Tensor:
    shape = list(shape)
    assert shape.count(-1) <= 1
    if -1 in shape:
        shape[shape.index(-1)] = int(x.size(-1) / -np.prod(shape))
    return x.view(*x.size()[:-1], *shape)


def _merge_last(x: torch.Tensor, n_dims: int) -> torch.Tensor:
    s = x.size()
    assert 1 < n_dims < len(s)
    return x.view(*s[:-n_dims], -1)


def _gelu(x: torch.Tensor) -> torch.Tensor:
    # The classic (erf) BERT gelu, as used upstream.
    return x * 0.5 * (1.0 + torch.erf(x / math.sqrt(2.0)))


class _LayerNorm(nn.Module):
    def __init__(self, cfg: LimuBertConfig, eps: float = 1e-12) -> None:
        super().__init__()
        self.gamma = nn.Parameter(torch.ones(cfg.hidden))
        self.beta = nn.Parameter(torch.zeros(cfg.hidden))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        u = x.mean(-1, keepdim=True)
        s = (x - u).pow(2).mean(-1, keepdim=True)
        x = (x - u) / torch.sqrt(s + self.eps)
        return self.gamma * x + self.beta


class _Embeddings(nn.Module):
    def __init__(self, cfg: LimuBertConfig) -> None:
        super().__init__()
        self.lin = nn.Linear(cfg.feature_num, cfg.hidden)
        self.pos_embed = nn.Embedding(cfg.seq_len, cfg.hidden)
        self.norm = _LayerNorm(cfg)
        self.emb_norm = cfg.emb_norm

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.size(1)
        pos = torch.arange(seq_len, dtype=torch.long, device=x.device)
        pos = pos.unsqueeze(0).expand(x.size(0), seq_len)
        e = self.lin(x)
        if self.emb_norm:
            e = self.norm(e)
        e = e + self.pos_embed(pos)
        return self.norm(e)


class _MultiHeadedSelfAttention(nn.Module):
    def __init__(self, cfg: LimuBertConfig) -> None:
        super().__init__()
        self.proj_q = nn.Linear(cfg.hidden, cfg.hidden)
        self.proj_k = nn.Linear(cfg.hidden, cfg.hidden)
        self.proj_v = nn.Linear(cfg.hidden, cfg.hidden)
        self.n_heads = cfg.n_heads

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        q, k, v = self.proj_q(x), self.proj_k(x), self.proj_v(x)
        q = _split_last(q, (self.n_heads, -1)).transpose(1, 2)
        k = _split_last(k, (self.n_heads, -1)).transpose(1, 2)
        v = _split_last(v, (self.n_heads, -1)).transpose(1, 2)
        scores = q @ k.transpose(-2, -1) / np.sqrt(k.size(-1))
        scores = func.softmax(scores, dim=-1)
        h = (scores @ v).transpose(1, 2).contiguous()
        return _merge_last(h, 2)


class _PositionWiseFeedForward(nn.Module):
    def __init__(self, cfg: LimuBertConfig) -> None:
        super().__init__()
        self.fc1 = nn.Linear(cfg.hidden, cfg.hidden_ff)
        self.fc2 = nn.Linear(cfg.hidden_ff, cfg.hidden)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc2(_gelu(self.fc1(x)))


class Transformer(nn.Module):
    """Weights shared across ``n_layers`` -- the distinctive LIMU-BERT trait."""

    def __init__(self, cfg: LimuBertConfig) -> None:
        super().__init__()
        self.embed = _Embeddings(cfg)
        self.n_layers = cfg.n_layers
        self.attn = _MultiHeadedSelfAttention(cfg)
        self.proj = nn.Linear(cfg.hidden, cfg.hidden)
        self.norm1 = _LayerNorm(cfg)
        self.pwff = _PositionWiseFeedForward(cfg)
        self.norm2 = _LayerNorm(cfg)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.embed(x)
        for _ in range(self.n_layers):
            h = self.attn(h)
            h = self.norm1(h + self.proj(h))
            h = self.norm2(h + self.pwff(h))
        return h


class LimuBertEncoder(nn.Module):
    """Wraps ``Transformer`` and mean-pools over time to one vector per window."""

    def __init__(self, cfg: LimuBertConfig, transformer: nn.Module) -> None:
        super().__init__()
        self.cfg = cfg
        self.transformer = transformer

    @torch.no_grad()
    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        # batch: (N, seq_len, feature_num) -> per-timestep (N, seq_len, hidden)
        hidden = self.transformer(batch)
        return hidden  # pooling is done by the caller


def _upstream_transformer(cfg: LimuBertConfig) -> nn.Module | None:
    src = os.environ.get("LIMU_BERT_SRC")
    if not src:
        return None
    src_path = Path(src)
    if not (src_path / "models.py").is_file():
        return None
    sys.path.insert(0, str(src_path))
    try:
        from models import Transformer as UpstreamTransformer  # type: ignore
    except Exception:
        return None
    from types import SimpleNamespace

    namespace = SimpleNamespace(
        feature_num=cfg.feature_num,
        hidden=cfg.hidden,
        hidden_ff=cfg.hidden_ff,
        n_layers=cfg.n_layers,
        n_heads=cfg.n_heads,
        seq_len=cfg.seq_len,
        emb_norm=cfg.emb_norm,
    )
    try:
        return UpstreamTransformer(namespace)
    except Exception:
        return None


def _extract_transformer_state(raw: object) -> dict[str, torch.Tensor]:
    """Accept a bare state_dict or a pickled model; return transformer.* weights."""
    if hasattr(raw, "state_dict") and callable(raw.state_dict):
        state = raw.state_dict()
    elif isinstance(raw, dict) and "state_dict" in raw and isinstance(raw["state_dict"], dict):
        state = raw["state_dict"]
    elif isinstance(raw, dict):
        state = raw
    else:
        return {}
    prefixed = {k: v for k, v in state.items() if k.startswith("transformer.")}
    if prefixed:
        return {k[len("transformer.") :]: v for k, v in prefixed.items()}
    # Already a plain transformer state_dict (no wrapper prefix).
    return dict(state)


def load_encoder(weights_path: Path, cfg: LimuBertConfig) -> tuple[LimuBertEncoder, dict]:
    """Build the encoder and load a pretrained checkpoint.

    Returns ``(encoder, report)`` where report has ``matched`` / ``missing`` /
    ``unexpected`` key counts so a bad checkpoint surfaces instead of running
    with random weights.
    """
    transformer = _upstream_transformer(cfg)
    used_upstream = transformer is not None
    if transformer is None:
        transformer = Transformer(cfg)

    raw = torch.load(weights_path, map_location="cpu", weights_only=False)
    state = _extract_transformer_state(raw)
    result = transformer.load_state_dict(state, strict=False)
    own_keys = set(transformer.state_dict().keys())
    matched = len(own_keys) - len(set(result.missing_keys))

    transformer.eval()
    encoder = LimuBertEncoder(cfg, transformer)
    encoder.eval()
    report = {
        "used_upstream_source": used_upstream,
        "checkpoint_keys": len(state),
        "encoder_params": len(own_keys),
        "matched": matched,
        "missing": list(result.missing_keys),
        "unexpected": list(result.unexpected_keys),
    }
    return encoder, report
