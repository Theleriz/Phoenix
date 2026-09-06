import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient } from "./client";
import { createTokenStore } from "./tokenStore";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("createApiClient", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("attaches the bearer token from the token store on authenticated requests", async () => {
    const tokenStore = createTokenStore("test-token");
    tokenStore.set("secret-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));
    const client = createApiClient({ tokenStore });

    await client.request("/api/v1/patients/me");

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer secret-token");
  });

  it("does not attach a token on requestNoAuth even when one is stored", async () => {
    const tokenStore = createTokenStore("test-token-2");
    tokenStore.set("secret-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ ok: true }));
    const client = createApiClient({ tokenStore });

    await client.requestNoAuth("/api/v1/demo");

    const [, init] = fetchMock.mock.calls[0];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBeNull();
  });

  it("clears the token and calls onUnauthorized exactly once on a 401, regardless of caller", async () => {
    const tokenStore = createTokenStore("test-token-3");
    tokenStore.set("stale-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ detail: "Invalid token" }, 401));
    const onUnauthorized = vi.fn();
    const client = createApiClient({ tokenStore, onUnauthorized });

    await expect(client.request("/api/v1/auth/me")).rejects.toBeInstanceOf(ApiError);

    expect(tokenStore.get()).toBeNull();
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("throws ApiError with the response status for any other non-2xx response", async () => {
    const tokenStore = createTokenStore("test-token-4");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ detail: "Episode not found" }, 404));
    const client = createApiClient({ tokenStore });

    const error = await client.request("/api/v1/patients/me").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
  });
});
