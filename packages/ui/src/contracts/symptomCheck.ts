/** Mirrors `POST /api/v1/rehab-sessions/{id}/symptom-check`. */

export interface SymptomCheckRequest {
  pain_before?: number;
  pain_after?: number;
  difficulty?: number;
  knee_feels?: "better" | "same" | "slightly_worse" | "much_worse";
  reported_symptoms: string[];
}

export interface SafetyAssessment {
  status: "evaluated" | "withheld";
  level: "GREEN" | "YELLOW" | "RED" | null;
  reasons: string[];
  policy_version: string | null;
}

export interface SymptomCheckResponse {
  symptom_check_id: string;
  assessment_id: string;
  safety_assessment: SafetyAssessment;
  alert_id: string | null;
}
