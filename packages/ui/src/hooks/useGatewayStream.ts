import { useEffect, useRef, useState } from "react";
import type { GatewayStreamEvent } from "../contracts/gateway";

export type GatewayStreamStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed";

export interface UseGatewayStreamHandlers {
  onEvent(event: GatewayStreamEvent): void;
  onError?(error: unknown): void;
}

export interface UseGatewayStreamResult {
  status: GatewayStreamStatus;
  /** Incremented on every reconnect. See the no-backfill note below. */
  reconnectCount: number;
}

const BACKOFF_STEPS_MS = [1000, 2000, 4000, 8000, 10000];

/**
 * Subscribes to `/api/v1/gateway/sessions/{sessionId}/stream`.
 *
 * The server sends no backfill/snapshot on connect (`GatewayStreams` in
 * `services/api/app/main.py` is a plain fan-out) -- every reconnect starts
 * from a blank slate and misses whatever happened while disconnected.
 * Callers MUST treat `reconnectCount > 0` as "status may be stale" (e.g. show
 * "reconnecting -- signal status may be out of date"), never silently resume
 * as if nothing was missed.
 */
export function useGatewayStream(
  sessionId: string | null,
  gatewayToken: string | null,
  handlers: UseGatewayStreamHandlers,
  baseUrl = ""
): UseGatewayStreamResult {
  const [status, setStatus] = useState<GatewayStreamStatus>("idle");
  const [reconnectCount, setReconnectCount] = useState(0);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!sessionId || !gatewayToken) {
      setStatus("idle");
      return;
    }
    let cancelled = false;
    let socket: WebSocket | null = null;
    let attempt = 0;
    let retryTimer: number | undefined;

    const streamUrl = () => {
      const url = new URL(
        `${baseUrl}/api/v1/gateway/sessions/${encodeURIComponent(sessionId)}/stream`,
        window.location.href
      );
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      return url.toString();
    };

    const connect = () => {
      if (cancelled) return;
      setStatus(attempt === 0 ? "connecting" : "reconnecting");
      // The token travels as a WS subprotocol, not `?token=` -- a query
      // string secret ends up in nginx access logs and browser history, a
      // subprotocol header does not (see `_websocket_gateway_token` in
      // services/api/app/main.py).
      socket = new WebSocket(streamUrl(), [gatewayToken]);
      socket.onopen = () => {
        if (cancelled) return;
        setStatus("open");
        attempt = 0;
      };
      socket.onmessage = (message) => {
        if (cancelled) return;
        try {
          handlersRef.current.onEvent(JSON.parse(message.data as string) as GatewayStreamEvent);
        } catch (error) {
          handlersRef.current.onError?.(error);
        }
      };
      socket.onerror = (error) => {
        handlersRef.current.onError?.(error);
      };
      socket.onclose = () => {
        if (cancelled) return;
        attempt += 1;
        setReconnectCount(attempt);
        const delay = BACKOFF_STEPS_MS[Math.min(attempt - 1, BACKOFF_STEPS_MS.length - 1)];
        retryTimer = window.setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      socket?.close();
      setStatus("closed");
    };
  }, [sessionId, gatewayToken, baseUrl]);

  return { status, reconnectCount };
}
