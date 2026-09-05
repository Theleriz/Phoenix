# PHOENIX IMU gateway

This is a technical scaffold, not a hardware-ready or clinical component. Its
only input source is the deterministic synthetic replay generator. The current
reverse-engineered `0x55 0x61` frame parser is deliberately unable to claim
checksum verification for physical hardware.

Run its tests from this directory:

```powershell
python -m unittest discover -s tests -v
```

Preview a synthetic three-sensor stream:

```powershell
python run_synthetic_replay.py
```

## WT901BLE68 diagnostic tools

These are **technical, non-clinical** diagnostics. None of them calculate
ROM, repetitions, score or clinical feedback. Do not record patient
identifiers in output filenames or file contents.

```powershell
cd services/imu-gateway
python -m pip install -e ".[ble]"

# Find nearby sensor addresses (power sensors on one at a time to tell them apart)
python scan_wt901ble68.py --seconds 8

# Inspect a single address' real GATT services/characteristics
python inspect_gatt.py <ADDRESS>

# Listen to raw notifications from one sensor, no frame parsing
python listen_raw.py <ADDRESS> --seconds 20

# Listen to raw notifications from all three sensors at once
python listen_raw_multi.py --seconds 20 `
  --sensor thigh=<ADDRESS> --sensor shank=<ADDRESS> --sensor foot=<ADDRESS>

# Capture parsed, sequence-numbered packets from all three sensors to JSONL
python capture_wt901ble68.py --seconds 60 --output captures/baseline.jsonl `
  --sensor thigh=<ADDRESS> `
  --sensor shank=<ADDRESS> `
  --sensor foot=<ADDRESS>
```

The three role-to-address mappings are deliberately explicit; the program
never infers a physical role from discovery order. Captures are ignored by
Git.

`capture_wt901ble68.py` parses the 20-byte `0x55 0x61` frame shape confirmed
against real hardware on 2026-09-05 (see
[`docs/imu/current-script-audit.md`](../../docs/imu/current-script-audit.md))
using the same `WitMotion61FrameBuffer`/`WitMotion61Parser` the gateway uses
for hardware-origin packets elsewhere. Every record is stamped
`origin: "hardware"` and `validation_status: "unverified_checksum"` — this
frame shape carries no checksum field, so packets must never be treated as
verified for clinical use.

In Docker Compose, `run_dev_replay.py` instead posts the same packets to the
local API using `PHOENIX_GATEWAY_TOKEN`; failed sends are replayed from its
durable JSONL buffer. The API persists them before its development-only
WebSocket fan-out. Configure hardware only after an approved protocol and UUID
configuration are available.

The command emits newline-delimited JSON. Every packet carries
`origin: "synthetic"` and `validation_status: "synthetic"`. These records
must not be presented as a patient measurement, supplied to scoring, or used
for clinical validation.
