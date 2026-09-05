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

In Docker Compose, `run_dev_replay.py` instead posts the same packets to the
local API using `PHOENIX_GATEWAY_TOKEN`; failed sends are replayed from its
durable JSONL buffer. The API persists them before its development-only
WebSocket fan-out. Configure hardware only after an approved protocol and UUID
configuration are available.

The command emits newline-delimited JSON. Every packet carries
`origin: "synthetic"` and `validation_status: "synthetic"`. These records
must not be presented as a patient measurement, supplied to scoring, or used
for clinical validation.
