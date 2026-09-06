"""Format-agnostic loader for the movement-interpretation checkpoint.

Put the downloaded model into ``services/api/app/ml/checkpoints/`` together
with a ``model_meta.json`` (copy ``model_meta.example.json``). If nothing is
there -- or the framework it needs is not installed -- ``load_model_bundle()``
returns ``None`` and inference abstains. That is the expected state until the
model is validated and clinically approved.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
META_FILENAME = "model_meta.json"

# Checked in this order; first match wins.
_WEIGHT_SUFFIXES = (".onnx", ".pt", ".pth", ".safetensors", ".bin")

Runner = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True, slots=True)
class ModelMeta:
    model_version: str
    feature_versions: tuple[str, ...]
    window_samples: int
    rate_hz: float
    channels: tuple[str, ...]
    sensor_order: tuple[str, ...]
    # "generic" (default): one call, batch shaped by input_layout below.
    # "limu_bert": vendored LIMU-BERT encoder, run once per sensor on the
    #   accel+gyro channels (6), embeddings fused across sensors. See
    #   ml.inference; extra carries feature_num/hidden/seq_len/emb_norm.
    framework: str
    # generic only: "N,T,S,C" (default) | "N,S,T,C" | "N,T,SC" | "N,S,TC"
    input_layout: str
    # {"kind": "zscore", "mean": [...], "std": [...]} |
    # {"kind": "scale", "factor": [...]} | {"kind": "limu"} | {} for none.
    normalization: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelBundle:
    meta: ModelMeta
    weights_path: Path
    runner: Runner
    load_report: dict[str, Any] = field(default_factory=dict)


def _load_meta(path: Path) -> ModelMeta:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ModelMeta(
        model_version=str(raw["model_version"]),
        feature_versions=tuple(raw.get("feature_versions", [])),
        window_samples=int(raw["window_samples"]),
        rate_hz=float(raw.get("rate_hz", 20.0)),
        channels=tuple(raw.get("channels", [])),
        sensor_order=tuple(raw.get("sensor_order", [])),
        framework=str(raw.get("framework", "generic")),
        input_layout=str(raw.get("input_layout", "N,T,S,C")),
        normalization=dict(raw.get("normalization", {})),
        extra=dict(raw.get("extra", {})),
    )


def find_checkpoint() -> tuple[Path, Path] | None:
    """Return ``(meta_path, weights_path)`` if a usable checkpoint is present."""
    meta_path = CHECKPOINT_DIR / META_FILENAME
    if not meta_path.is_file():
        return None
    for suffix in _WEIGHT_SUFFIXES:
        hits = sorted(CHECKPOINT_DIR.glob(f"*{suffix}"))
        if hits:
            return meta_path, hits[0]
    return None


def load_model_bundle() -> ModelBundle | None:
    found = find_checkpoint()
    if found is None:
        return None
    meta_path, weights_path = found
    try:
        meta = _load_meta(meta_path)
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
    built = _build_runner(weights_path, meta)
    if built is None:
        return None
    runner, load_report = built
    return ModelBundle(
        meta=meta, weights_path=weights_path, runner=runner, load_report=load_report
    )


def _build_runner(weights_path: Path, meta: ModelMeta) -> tuple[Runner, dict[str, Any]] | None:
    """Return ``(ndarray -> ndarray callable, load_report)`` or ``None``.

    torch / onnxruntime are imported lazily so the API never hard-depends on
    them; a missing framework just means "abstain".
    """
    if meta.framework == "limu_bert":
        return _build_limu_bert_runner(weights_path, meta)

    suffix = weights_path.suffix.lower()

    if suffix == ".onnx":
        try:
            import onnxruntime as ort
        except ImportError:
            return None
        session = ort.InferenceSession(
            str(weights_path), providers=["CPUExecutionProvider"]
        )
        input_name = session.get_inputs()[0].name

        def run_onnx(batch: np.ndarray) -> np.ndarray:
            outputs = session.run(None, {input_name: batch.astype(np.float32)})
            return np.asarray(outputs[0], dtype=np.float32)

        return run_onnx, {"kind": "onnx"}

    if suffix in (".pt", ".pth", ".safetensors", ".bin"):
        try:
            import torch
        except ImportError:
            return None
        try:
            obj = torch.load(weights_path, map_location="cpu", weights_only=False)
        except Exception:
            return None
        if not callable(obj) or not hasattr(obj, "eval"):
            # A bare state_dict / config: needs the model class (use framework
            # "limu_bert", or an .onnx export).
            return None
        obj.eval()

        def run_torch(batch: np.ndarray) -> np.ndarray:
            with torch.no_grad():
                output = obj(torch.from_numpy(np.ascontiguousarray(batch, dtype=np.float32)))
            return output.detach().cpu().numpy().astype(np.float32)

        return run_torch, {"kind": "torch_module"}

    return None


def _build_limu_bert_runner(
    weights_path: Path, meta: ModelMeta
) -> tuple[Runner, dict[str, Any]] | None:
    """LIMU-BERT encoder runner: ``(N, seq_len, 6) -> (N, seq_len, hidden)``."""
    try:
        import torch

        from .limu_bert.config import LimuBertConfig
        from .limu_bert.encoder import load_encoder
    except ImportError:
        return None

    cfg = LimuBertConfig.from_meta({**meta.extra, "seq_len": meta.window_samples})
    try:
        encoder, report = load_encoder(weights_path, cfg)
    except (OSError, RuntimeError, ValueError, KeyError):
        return None

    def run_limu(batch: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            tensor = torch.from_numpy(np.ascontiguousarray(batch, dtype=np.float32))
            output = encoder(tensor)
        return output.detach().cpu().numpy().astype(np.float32)

    return run_limu, {"kind": "limu_bert", **report}
