"""Vendored LIMU-BERT encoder for local, in-process representation extraction.

Upstream: https://github.com/dapowan/LIMU-BERT-Public (MIT License).
``encoder.py`` is a faithful re-implementation of the parameter-shared
Transformer encoder from upstream ``models.py`` -- enough to load a pretrained
``pretrain_base_*_20_120`` checkpoint's ``transformer.*`` weights and produce
representations. It does NOT include the pre-training decoder or masking.

If a checkpoint's ``state_dict`` keys do not line up with this
re-implementation, set the env var ``LIMU_BERT_SRC`` to a checkout of the
upstream repo; ``encoder.py`` then imports the canonical ``models.Transformer``.

``encoder`` imports torch, so import it lazily (``model.py`` does). ``config``
is torch-free.
"""

from __future__ import annotations

from .config import LIMU_BASE_V1, LimuBertConfig

__all__ = ["LIMU_BASE_V1", "LimuBertConfig"]
