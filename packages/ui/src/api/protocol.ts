import type { ApiClient } from "./client";
import type {
  CurrentProtocol,
  ExerciseDefinition,
  ProtocolHistoryEntry,
  ProtocolVersionRequest,
  ProtocolVersionResponse,
} from "../contracts/protocol";

export function createProtocolApi(client: ApiClient) {
  return {
    listExerciseDefinitions: () => client.request<ExerciseDefinition[]>("/api/v1/exercise-definitions"),
    current: (episodeId: string) =>
      client.request<CurrentProtocol>(`/api/v1/episodes/${encodeURIComponent(episodeId)}/protocol`),
    history: (episodeId: string) =>
      client.request<ProtocolHistoryEntry[]>(`/api/v1/episodes/${encodeURIComponent(episodeId)}/protocol-history`),
    createVersion: (episodeId: string, request: ProtocolVersionRequest) =>
      client.request<ProtocolVersionResponse>(
        `/api/v1/episodes/${encodeURIComponent(episodeId)}/protocol-versions`,
        { method: "POST", body: JSON.stringify(request) }
      ),
  };
}
