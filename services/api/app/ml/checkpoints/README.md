# Movement-interpretation checkpoint

**Put the model here.** Nothing in this directory is committed (see
`.gitignore`); in production it is baked into the API image or mounted.

The chosen model is **LIMU-BERT** (https://github.com/dapowan/LIMU-BERT-Public,
MIT), `base_v1` config, run **per sensor** on the 6 accel+gyro channels.

## What to drop here

1. **The pretrained weights**, e.g. from the upstream repo
   `saved/pretrain_base_uci_20_120/` (or your own `pretrain.py` output).
   A `.pt` / `.pth` state_dict is expected — the file may be either a bare
   `transformer.*` state_dict or the full `LIMUBertModel4Pretrain` state_dict;
   the loader takes the `transformer.*` subset from both.

2. **`model_meta.json`** — copy `model_meta.example.json`. Key fields for LIMU:
   - `framework`: `"limu_bert"`
   - `window_samples`: **120** (must equal the checkpoint's `seq_len`; the
     positional embedding is a fixed table)
   - `rate_hz`: `20`
   - `normalization`: `{"kind": "limu"}` (accel /9.8, gyro untouched — mirrors
     upstream `Preprocess4Normalization(6)`)
   - `extra.feature_num`: `6`, plus `hidden/hidden_ff/n_layers/n_heads/emb_norm`

## How it runs

`ml.input.build_model_input` → `(T, 3, 9)` float32 (accel g, gyro deg/s, orient
deg). Then `ml.inference._run_limu_bert`:

1. cut `window_samples`-long windows at 50 % overlap → `(N, 120, 3, 9)`
2. `to_limu_units`: accel g→m/s², gyro deg/s→rad/s
3. `normalization {"kind":"limu"}`: accel /9.8
4. for each sensor: feed `(N, 120, 6)` (accel+gyro only) to the encoder →
   `(N, 120, 72)`, mean-pool over time → `(N, 72)`
5. concat the 3 sensor vectors → `(N, 216)`, mean over windows → `216`-d
   `embedding` stored in `shadow_predictions`

Orientation (channels 6:9) is **not** used here — upstream slot 6:9 is
magnetometer. Orientation goes to the deterministic branch (`ml/metrics.py`).

## Vendored encoder

`ml/limu_bert/encoder.py` re-implements the upstream parameter-shared
`Transformer` so a checkpoint loads without cloning the repo. `load_encoder`
loads with `strict=False` and the `load_report` (matched / missing / unexpected
key counts) is stored in the prediction — **check it**. If keys don't line up,
set env `LIMU_BERT_SRC=/path/to/LIMU-BERT-Public` and the loader imports the
canonical `models.Transformer` instead.

## Enabling torch

`pip install -r services/api/requirements-ml.txt` (CPU torch). Without it
`load_model_bundle()` returns `None` and inference abstains — nothing else
changes. After adding the file at runtime, call
`ml.inference.reset_model_cache()`.

## Caveat

The released checkpoints were pretrained on **phone** IMU datasets. Zero-shot
on 3 leg-strapped WT901 sensors at ~10 Hz (upsampled) is a large domain shift —
treat the embedding as a pipeline smoke test, not a real feature, until you
pretrain on your own data.
