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
        self.assertIn("await client.preprocess", self.api_source)
        self.assertIn("INSERT INTO derived_metrics", self.api_source)
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
