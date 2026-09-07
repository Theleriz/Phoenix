import type { ApiClient } from "./client";
import type { Patient, PatientWithEpisode } from "../contracts/patients";

export function createPatientsApi(client: ApiClient) {
  return {
    /** Self-lookup: the only authenticated way for a patient to learn their own patient_id/episode_id. */
    me: () => client.request<PatientWithEpisode>("/api/v1/patients/me"),
    /** Org-scoped list for a clinician's dashboard queue. */
    list: () => client.request<PatientWithEpisode[]>("/api/v1/patients"),
    get: (patientId: string) => client.request<Patient>(`/api/v1/patients/${encodeURIComponent(patientId)}`),
  };
}
