/** Mirrors the protocol/prescription shapes in `services/api/app/main.py`. */

export interface PrescriptionConfiguration {
  sets: number | null;
  repetitions: number | null;
  frequency: string | null;
  target_rom_degrees: number | null;
  tempo: string | null;
  hold_seconds: number | null;
  restriction_sources: Record<string, unknown>[];
  approval_state?: "draft" | "clinically_approved";
}

export interface ExerciseDefinition {
  id: string;
  name: string;
  version: number;
  configuration: Record<string, unknown>;
}

export interface ProtocolTemplateSummary {
  id: string;
  name: string;
  approval_state: string;
}

export interface ProtocolExercise {
  id: string;
  name: string;
  version: number;
  prescription_id: string;
  prescription: PrescriptionConfiguration;
}

export interface CurrentProtocol {
  assignment_id: string;
  version: number;
  template: ProtocolTemplateSummary;
  exercises: ProtocolExercise[];
}

export interface ProtocolHistoryEntry {
  assignment_id: string;
  version: number;
  created_at: string;
  superseded_at: string | null;
  exercise: { id: string; name: string; version: number };
  prescription_id: string;
  prescription: PrescriptionConfiguration;
}

export interface ProtocolVersionRequest {
  protocol_template_id: string;
  exercise_definition_id: string;
  prescription: Partial<PrescriptionConfiguration>;
}

export interface ProtocolVersionResponse {
  assignment_id: string;
  prescription_id: string;
  version: number;
}
