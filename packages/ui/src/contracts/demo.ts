/** Mirrors the unauthenticated fixture in `services/api/app/demo.py`. */

export interface DemoPatientRow {
  id: string;
  display_name: string;
  procedure: string;
  pod: number;
  adherence_pct: number;
  rom_trend: "up" | "flat" | "down";
  pain: number;
  status: "stable" | "review" | "urgent";
}

export interface DemoSnapshot {
  organization: { id: string; name: string };
  patient: { id: string; display_name: string; post_op_day: number };
  clinician: { id: string; display_name: string };
  protocol: { id: string; name: string };
  replay_session: {
    id: string;
    origin: string;
    validation_status: string;
    sensor_roles: string[];
    frame_count: number;
  };
  patients: DemoPatientRow[];
  safety_notice: string;
}
