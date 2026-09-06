/** Mirrors `GET /api/v1/episodes/{id}/alerts` and `POST /api/v1/alerts/{id}/actions`. */

export type AlertSeverity = "green" | "yellow" | "red";

export interface Alert {
  id: string;
  severity: AlertSeverity;
  rule_version: string;
  trigger: Record<string, unknown>;
  created_at: string;
  status: "open" | "acknowledged" | "dismissed";
}

export interface AlertActionRequest {
  action_type: "acknowledged" | "dismissed";
  note?: string;
}

export interface AlertActionResponse {
  action_id: string;
  alert_id: string;
  status: string;
}
