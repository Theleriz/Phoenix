import type { ApiClient } from "./client";
import type { SymptomCheckRequest, SymptomCheckResponse } from "../contracts/symptomCheck";

export function createSymptomCheckApi(client: ApiClient) {
  return {
    submit: (sessionId: string, request: SymptomCheckRequest) =>
      client.request<SymptomCheckResponse>(
        `/api/v1/rehab-sessions/${encodeURIComponent(sessionId)}/symptom-check`,
        { method: "POST", body: JSON.stringify(request) }
      ),
  };
}
