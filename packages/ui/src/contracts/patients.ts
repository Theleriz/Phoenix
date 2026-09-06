/** Mirrors `GET /api/v1/patients`, `/patients/me`, `/patients/{patient_id}`. */

export interface Patient {
  id: string;
  display_name: string;
  post_op_day: number;
}

export interface PatientWithEpisode extends Patient {
  active_episode_id: string | null;
}
