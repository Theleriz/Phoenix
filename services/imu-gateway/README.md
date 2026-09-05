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

## WT901BLE68 diagnostic baseline capture

This is a **technical, non-clinical capture**. It verifies BLE connectivity,
the confirmed 11-byte `0x55 0x61` angles packet and checksum. It does not
calculate ROM, repetitions, score or clinical feedback. Do not record patient
identifiers in the output filename or file contents.

```powershell
cd services/imu-gateway
python -m pip install -e ".[ble]"
python capture_wt901ble68.py --seconds 60 --output captures/baseline.jsonl `
  --sensor thigh=AA:BB:CC:DD:EE:01 `
  --sensor shank=AA:BB:CC:DD:EE:02 `
  --sensor foot=AA:BB:CC:DD:EE:03
```

The three role-to-address mappings are deliberately explicit; the program
never infers a physical role from discovery order. Captures are ignored by Git.

In Docker Compose, `run_dev_replay.py` instead posts the same packets to the
local API using `PHOENIX_GATEWAY_TOKEN`; failed sends are replayed from its
durable JSONL buffer. The API persists them before its development-only
WebSocket fan-out. Configure hardware only after an approved protocol and UUID
configuration are available.

The command emits newline-delimited JSON. Every packet carries
`origin: "synthetic"` and `validation_status: "synthetic"`. These records
must not be presented as a patient measurement, supplied to scoring, or used
for clinical validation.
