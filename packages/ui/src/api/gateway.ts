import { ApiError, type ApiClient } from "./client";
import type {
  ExerciseAttemptRequest,
  ExerciseAttemptResponse,
  GatewayIMUPacket,
  GatewayIngestResponse,
  SensorDeviceRequest,
  SensorDeviceResponse,
  SignalQualityResponse,
} from "../contracts/gateway";

export function createGatewayApi(client: ApiClient) {
  return {
    startExerciseAttempt: (episodeId: string, request: ExerciseAttemptRequest) =>
      client.request<ExerciseAttemptResponse>(
        `/api/v1/episodes/${encodeURIComponent(episodeId)}/exercise-attempts`,
        { method: "POST", body: JSON.stringify(request) }
      ),
    completeExerciseAttempt: (attemptId: string) =>
      client.request<{ exercise_attempt_id: string; status: string }>(
        `/api/v1/exercise-attempts/${encodeURIComponent(attemptId)}/complete`,
        { method: "POST" }
      ),
    registerSensorDevice: (request: SensorDeviceRequest) =>
      client.request<SensorDeviceResponse>("/api/v1/sensor-devices", {
        method: "POST",
        body: JSON.stringify(request),
      }),
    signalQuality: (sessionId: string) =>
      client.request<SignalQualityResponse>(
        `/api/v1/rehab-sessions/${encodeURIComponent(sessionId)}/signal-quality`
      ),
  };
}

/**
 * Posts one raw sensor packet directly to the gateway ingest endpoint.
 *
 * This bypasses `ApiClient` deliberately: ingestion is authenticated with
 * `PHOENIX_GATEWAY_TOKEN` (a shared gateway secret), not the user's own
 * bearer token -- the two must never be attached to the same request.
 */
export async function ingestImuPacket(
  baseUrl: string,
  gatewayToken: string,
  packet: GatewayIMUPacket
): Promise<GatewayIngestResponse> {
  const response = await fetch(`${baseUrl}/api/v1/gateway/imu-packets`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${gatewayToken}`,
    },
    body: JSON.stringify(packet),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => undefined);
    throw new ApiError(response.status, body);
  }
  return response.json();
}
