-- Stage 15: a resent or replayed packet must not create a second raw event
-- and a second raw_imu_chunk for the same (session, sensor, sequence).
--
-- The gateway assigns a monotonic sequence_number per sensor role; the same
-- triple can only ever describe one physical sample. This unique index is the
-- integrity backstop behind the application-level duplicate check in
-- app/main.py::ingest_imu_packet, and also closes the concurrent-retry race
-- that check alone cannot.

CREATE UNIQUE INDEX gateway_packet_events_session_role_sequence_key
    ON gateway_packet_events (rehab_session_id, sensor_role, sequence_number);
