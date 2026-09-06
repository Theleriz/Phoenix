import unittest
from pathlib import Path


class GatewayIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).parents[1]
        self.api_source = (root / "app" / "main.py").read_text(encoding="utf-8")
        migration_path = root / "migrations" / "versions" / "0006_gateway_ingestion.sql"
        self.migration = migration_path.read_text(encoding="utf-8")
        quality_path = root / "migrations" / "versions" / "0007_signal_quality.sql"
        self.quality_migration = quality_path.read_text(encoding="utf-8")
        calibration_path = root / "migrations" / "versions" / "0009_static_calibration_gate.sql"
        self.calibration_migration = calibration_path.read_text(encoding="utf-8")
        dedup_path = root / "migrations" / "versions" / "0015_gateway_packet_dedup.sql"
        self.dedup_migration = dedup_path.read_text(encoding="utf-8")

    def test_ingestion_is_authenticated_persisted_and_then_published(self) -> None:
        self.assertIn('"/api/v1/gateway/imu-packets"', self.api_source)
        self.assertIn("require_gateway_authorization(authorization)", self.api_source)
        self.assertIn("INSERT INTO raw_imu_chunks", self.api_source)
        self.assertIn("INSERT INTO gateway_packet_events", self.api_source)
        self.assertIn("evaluate_signal_quality", self.api_source)
        self.assertIn("INSERT INTO signal_quality", self.api_source)
        self.assertIn("INSERT INTO calibrations", self.api_source)
        self.assertIn("preprocess_transport_events(", self.api_source)
        self.assertIn("INSERT INTO derived_metrics", self.api_source)
        self.assertIn("run_shadow_inference(", self.api_source)
        self.assertIn("INSERT INTO shadow_predictions", self.api_source)
        self.assertIn('"/api/v1/rehab-sessions/{session_id}/signal-quality"', self.api_source)
        self.assertIn("signal_quality_not_available", self.api_source)
        self.assertLess(
            self.api_source.index("INSERT INTO gateway_packet_events"),
            self.api_source.index("await gateway_streams.publish"),
        )

    def test_migration_keeps_raw_payloads_append_only(self) -> None:
        self.assertIn("CREATE TABLE gateway_packet_events", self.migration)
        self.assertIn("gateway_packet_events_immutable", self.migration)
        self.assertIn("synthetic-session-v1", self.migration)
        self.assertIn("algorithm-signal-quality-v1", self.quality_migration)
        self.assertIn("algorithm-static-calibration-gate-v1", self.calibration_migration)

    def test_replayed_packet_is_rejected_before_it_duplicates_a_chunk(self) -> None:
        self.assertIn("CREATE UNIQUE INDEX", self.dedup_migration)
        self.assertIn(
            "(rehab_session_id, sensor_role, sequence_number)", self.dedup_migration
        )
        # The duplicate check must run before the raw_imu_chunks insert.
        self.assertIn('detail="Duplicate gateway packet"', self.api_source)
        self.assertLess(
            self.api_source.index('detail="Duplicate gateway packet"'),
            self.api_source.index("INSERT INTO raw_imu_chunks"),
        )

    def test_session_recompute_is_bounded(self) -> None:
        self.assertIn(
            "FROM gateway_packet_events\n               WHERE rehab_session_id = %s "
            "ORDER BY received_at, id LIMIT 6000",
            self.api_source,
        )

    def test_preprocessing_metric_failure_does_not_sink_the_raw_event(self) -> None:
        self.assertIn("except psycopg.Error:", self.api_source)
        self.assertIn('preprocessing["metric_persisted"] = False', self.api_source)

    def test_websocket_echoes_back_the_negotiated_subprotocol(self) -> None:
        # A client offering Sec-WebSocket-Protocol values (browsers must use
        # this, not `?token=`, to keep a bearer secret out of logs/history)
        # requires the server to echo one back on accept(), or browsers abort
        # the connection even after a 101 handshake -- confirmed against a
        # real browser client, not just this source check.
        self.assertIn("subprotocol: str | None = None", self.api_source)
        self.assertIn("await client.accept(subprotocol=subprotocol)", self.api_source)
        self.assertIn("negotiated_protocol = requested_protocol.split", self.api_source)
        self.assertIn("subprotocol=negotiated_protocol", self.api_source)

    def test_ingest_response_type_matches_its_nested_dict_body(self) -> None:
        # The response includes nested dicts (signal_quality, preprocessing) and
        # a nullable string (preprocessing_metric_id) -- a `dict[str, str]`
        # return annotation makes FastAPI's response validation 500 on every
        # successful ingest (caught by a live end-to-end run, not by the
        # source-string tests in this file).
        start = self.api_source.index("async def ingest_imu_packet(")
        signature_end = self.api_source.index(":", self.api_source.index(") ->", start))
        signature = self.api_source[start:signature_end]
        self.assertIn("-> dict[str, object]", signature)
