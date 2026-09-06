"""LIMU-BERT model config (mirrors upstream ``config/limu_bert.json``)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LimuBertConfig:
    feature_num: int = 6
    hidden: int = 72
    hidden_ff: int = 144
    n_layers: int = 4
    n_heads: int = 4
    seq_len: int = 120
    # Not in limu_bert.json; upstream default is True.
    emb_norm: bool = True

    @classmethod
    def from_meta(cls, extra: dict) -> LimuBertConfig:
        return cls(
            feature_num=int(extra.get("feature_num", 6)),
            hidden=int(extra.get("hidden", 72)),
            hidden_ff=int(extra.get("hidden_ff", 144)),
            n_layers=int(extra.get("n_layers", 4)),
            n_heads=int(extra.get("n_heads", 4)),
            seq_len=int(extra.get("seq_len", 120)),
            emb_norm=bool(extra.get("emb_norm", True)),
        )


# Upstream "base_v1": the pretrained pretrain_base_*_20_120 checkpoints.
LIMU_BASE_V1 = LimuBertConfig()
