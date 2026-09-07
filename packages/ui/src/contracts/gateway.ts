/**
 * Mirrors the gateway wire contract in `services/api/app/main.py`
 * (`GatewayIMUPacket`) and the IMU gateway's `normalize_packet()` output
 * (`services/imu-gateway/src/phoenix_imu_gateway/transport.py`). This flat
 * shape -- not the gateway's internal `RawIMUPacket` -- is what crosses the
 * wire to/from the API.
 */

export type SensorRole = "thigh" | "shank" | "foot";
export type PacketOrigin = "synthetic" | "hardware";

export interface GatewayIMUPacket {
  session_id: string;
  device_id: string;
  sensor_role: SensorRole;
  timestamp_device: number | null;
  timestamp_gateway: string;
  sequence_number: number;
  ax: number;
  ay: number;
  az: number;
  gx: number;
  gy: number;
  gz: number;
  orientation_euler_degrees: [number, number, number] | null;
  battery: number | null;
  origin: PacketOrigin;
  validation_status: string;
  adapter_version: string;
}

export type SignalQualityLevel = "HIGH" | "MEDIUM" | "LOW" | "INVALID";

export interface SignalQualityReport {
  level: SignalQualityLevel;
  reasons: string[];
  calibration_duration_seconds: number;
  synchronization_skew_ms: number | null;
  sample_rates_hz: Partial<Record<SensorRole, number>>;
  packet_counts: Partial<Record<SensorRole, number>>;
  scoring_permitted: boolean;
  calibration_recorded: boolean;
}

export interface PreprocessingResult {
  status: "skipped_quality_gate" | "completed" | "blocked" | "unavailable" | "not_configured";
  reasons?: string[];
  parameters?: Record<string, unknown>;
  frame_count?: number;
  metric_persisted?: boolean;
}

/**
 * Deterministic repetition signal. `window_count` is reps detected in the
 * recent analysis window (it can plateau/reset as the window slides); the
 * patient app keeps its own cumulative counter and increments it on each
 * `just_completed` with a new `last_completed_at`.
 */
export interface RepetitionSignal {
  window_count: number;
  target: number | null;
  just_completed: boolean;
  last_completed_at: number | null;
  amplitude_degrees: number;
  proxy: string;
  reason: string | null;
  persisted?: boolean;
}

export interface GatewayIngestResponse {
  event_id: string;
  raw_imu_chunk_id: string;
  signal_quality: SignalQualityReport;
  preprocessing: PreprocessingResult;
  preprocessing_metric_id: string | null;
  repetitions: RepetitionSignal | null;
}

/** One WebSocket stream message: the ingested packet plus its derived context. */
export type GatewayStreamEvent = GatewayIMUPacket & {
  event_id: string;
  signal_quality: SignalQualityReport;
  preprocessing: PreprocessingResult;
  preprocessing_metric_id: string | null;
  repetitions: RepetitionSignal | null;
};

export interface SignalQualityResponse {
  session_id: string;
  assessed_at?: string;
  clinical_scoring: false;
  level: SignalQualityLevel;
  reasons: string[];
  scoring_permitted: boolean;
  calibration_duration_seconds?: number;
  synchronization_skew_ms?: number | null;
  sample_rates_hz?: Partial<Record<SensorRole, number>>;
  packet_counts?: Partial<Record<SensorRole, number>>;
  calibration_recorded?: boolean;
}

export interface ExerciseAttemptRequest {
  source_kind: PacketOrigin;
  exercise_prescription_id: string;
}

export interface ExerciseAttemptResponse {
  session_id: string;
  exercise_attempt_id: string;
}

export interface SensorDeviceRequest {
  device_identifier: string;
  model?: string | null;
}

export interface SensorDeviceResponse {
  id: string;
}
