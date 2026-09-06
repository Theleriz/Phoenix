import type { ApiClient } from "./client";
import type { Alert, AlertActionRequest, AlertActionResponse } from "../contracts/alerts";

export function createAlertsApi(client: ApiClient) {
  return {
    list: (episodeId: string) => client.request<Alert[]>(`/api/v1/episodes/${encodeURIComponent(episodeId)}/alerts`),
    act: (alertId: string, request: AlertActionRequest) =>
      client.request<AlertActionResponse>(`/api/v1/alerts/${encodeURIComponent(alertId)}/actions`, {
        method: "POST",
        body: JSON.stringify(request),
      }),
  };
}
