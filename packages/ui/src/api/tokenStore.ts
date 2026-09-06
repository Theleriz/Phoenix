/**
 * Persists the bearer token in `localStorage`, not memory-only.
 *
 * Tradeoff: unlike an httpOnly cookie, anything with script execution on the
 * page (XSS) can read this. The API does not issue cookie sessions today, so
 * this is the pragmatic choice for a scaffold stage -- an in-memory-only
 * store would log the patient out on every page refresh, which is poor UX
 * for a rehab session someone dips into several times a day. Revisit if the
 * API grows an httpOnly-cookie login path.
 */
export interface TokenStore {
  get(): string | null;
  set(token: string): void;
  clear(): void;
  subscribe(listener: (token: string | null) => void): () => void;
}

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Private browsing / storage disabled: fall back to in-memory only.
  }
}

export function createTokenStore(storageKey: string): TokenStore {
  let cached: string | null = readStorage(storageKey);
  const listeners = new Set<(token: string | null) => void>();

  const notify = () => {
    for (const listener of listeners) listener(cached);
  };

  return {
    get: () => cached,
    set(token: string) {
      cached = token;
      writeStorage(storageKey, token);
      notify();
    },
    clear() {
      cached = null;
      writeStorage(storageKey, null);
      notify();
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
