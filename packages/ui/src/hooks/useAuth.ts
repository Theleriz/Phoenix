import { useCallback, useEffect, useState } from "react";
import type { PhoenixApi } from "../api";
import type { TokenStore } from "../api/tokenStore";
import type { MeResponse } from "../contracts/auth";

export interface UseAuthResult {
  identity: MeResponse | null;
  loading: boolean;
  login(email: string, password: string, organizationId: string): Promise<void>;
  logout(): void;
}

export function useAuth(api: PhoenixApi, tokenStore: TokenStore): UseAuthResult {
  const [identity, setIdentity] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) {
      setIdentity(null);
      setLoading(false);
      return;
    }
    try {
      setIdentity(await api.auth.me());
    } catch {
      setIdentity(null);
    } finally {
      setLoading(false);
    }
  }, [api, tokenStore]);

  useEffect(() => {
    void refresh();
    // The api client's 401 interceptor clears the store on expiry; reflect
    // that here too so a screen relying on `identity` unmounts promptly.
    return tokenStore.subscribe((token) => {
      if (!token) setIdentity(null);
    });
  }, [refresh, tokenStore]);

  const login = useCallback(
    async (email: string, password: string, organizationId: string) => {
      const { access_token } = await api.auth.login({
        email,
        password,
        organization_id: organizationId,
      });
      tokenStore.set(access_token);
      await refresh();
    },
    [api, tokenStore, refresh]
  );

  const logout = useCallback(() => {
    tokenStore.clear();
    setIdentity(null);
  }, [tokenStore]);

  return { identity, loading, login, logout };
}
