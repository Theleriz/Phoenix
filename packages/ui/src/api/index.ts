import { type ApiClientOptions, createApiClient } from "./client";
import { createAlertsApi } from "./alerts";
import { createAuthApi } from "./auth";
import { createDemoApi } from "./demo";
import { createGatewayApi } from "./gateway";
import { createPatientsApi } from "./patients";
import { createProtocolApi } from "./protocol";
import { createSymptomCheckApi } from "./symptomCheck";

export function createPhoenixApi(options: ApiClientOptions) {
  const client = createApiClient(options);
  return {
    client,
    auth: createAuthApi(client),
    patients: createPatientsApi(client),
    protocol: createProtocolApi(client),
    gateway: createGatewayApi(client),
    alerts: createAlertsApi(client),
    symptomCheck: createSymptomCheckApi(client),
    demo: createDemoApi(client),
  };
}

export type PhoenixApi = ReturnType<typeof createPhoenixApi>;

export { ApiError } from "./client";
export type { ApiClient, ApiClientOptions } from "./client";
export { createTokenStore } from "./tokenStore";
export type { TokenStore } from "./tokenStore";
export { ingestImuPacket } from "./gateway";
