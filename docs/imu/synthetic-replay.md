# Synthetic IMU replay

## Purpose

The development-only replay source in `services/imu-gateway` allows frontend,
transport and contract work without BLE hardware. It emits 15 deterministic
frames (five time points for each explicitly configured `THIGH`, `SHANK` and
`FOOT` role). The waveform resembles movement only so applications can render
changing values; it is not a biomechanical measurement, repetition or ROM.

## Safety boundary

Every sample is stamped with:

- `origin = synthetic`;
- `validation_status = synthetic`;
- `adapter_version = 0.1.0`.

Synthetic records are prohibited from clinical scoring, feedback, alerts,
algorithm validation, medical summaries and patient records. Real packets
parsed from the currently known 20-byte shape receive
`unverified_checksum`, and downstream code must reject that status for scoring
until the official protocol is supplied and a checksum verifier is implemented.

## Run

From `services/imu-gateway`:

```powershell
python -m unittest discover -s tests -v
python run_synthetic_replay.py
```

The second command is an NDJSON preview. It has no BLE dependency and makes no
network request. A real BLE adapter is intentionally not included yet: the
model, UUIDs, checksum, ranges and timing contract are still unknown.
