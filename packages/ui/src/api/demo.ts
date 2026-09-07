import type { ApiClient } from "./client";
import type { DemoSnapshot } from "../contracts/demo";

export function createDemoApi(client: ApiClient) {
  return {
    /** Unauthenticated fixture -- also used to pre-fill the login screen's organization field. */
    get: () => client.requestNoAuth<DemoSnapshot>("/api/v1/demo"),
  };
}
