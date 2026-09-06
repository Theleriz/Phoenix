import type { ApiClient } from "./client";
import type { LoginRequest, LoginResponse, MeResponse } from "../contracts/auth";

export function createAuthApi(client: ApiClient) {
  return {
    login: (request: LoginRequest) =>
      client.requestNoAuth<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(request),
      }),
    me: () => client.request<MeResponse>("/api/v1/auth/me"),
  };
}
