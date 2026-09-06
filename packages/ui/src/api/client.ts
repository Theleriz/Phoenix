import type { TokenStore } from "./tokenStore";

export interface ApiClientOptions {
  /** Defaults to same-origin (empty string) -- both apps proxy `/api/` via nginx. */
  baseUrl?: string;
  tokenStore: TokenStore;
  /** Called once, centrally, whenever any request comes back 401 -- so individual screens never special-case token expiry. */
  onUnauthorized?: () => void;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown
  ) {
    super(`API request failed with status ${status}`);
  }
}

export interface ApiClient {
  request<T>(path: string, init?: RequestInit): Promise<T>;
  requestNoAuth<T>(path: string, init?: RequestInit): Promise<T>;
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

export function createApiClient({ baseUrl = "", tokenStore, onUnauthorized }: ApiClientOptions): ApiClient {
  async function send<T>(path: string, init: RequestInit, attachAuth: boolean): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body !== undefined) headers.set("Content-Type", "application/json");
    if (attachAuth) {
      const token = tokenStore.get();
      if (token) headers.set("Authorization", `Bearer ${token}`);
    }
    const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
    if (response.status === 401) {
      tokenStore.clear();
      onUnauthorized?.();
      throw new ApiError(401, await safeJson(response));
    }
    if (!response.ok) {
      throw new ApiError(response.status, await safeJson(response));
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  return {
    request: (path, init) => send(path, init ?? {}, true),
    requestNoAuth: (path, init) => send(path, init ?? {}, false),
  };
}
