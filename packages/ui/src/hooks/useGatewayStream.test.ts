import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useGatewayStream } from "./useGatewayStream";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  protocols: string[];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((error: unknown) => void) | null = null;
  closed = false;

  constructor(url: string, protocols: string[] = []) {
    this.url = url;
    this.protocols = protocols;
    FakeWebSocket.instances.push(this);
  }

  close(): void {
    this.closed = true;
    this.onclose?.();
  }
}

describe("useGatewayStream", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("sends the gateway token as a WS subprotocol, not a query string", () => {
    renderHook(() => useGatewayStream("session-1", "gw-token", { onEvent: vi.fn() }));

    expect(FakeWebSocket.instances).toHaveLength(1);
    const socket = FakeWebSocket.instances[0];
    expect(socket.protocols).toEqual(["gw-token"]);
    expect(socket.url).not.toContain("token=gw-token");
    expect(socket.url).toContain("/api/v1/gateway/sessions/session-1/stream");
  });

  it("does not connect when sessionId or gatewayToken is missing", () => {
    renderHook(() => useGatewayStream(null, "gw-token", { onEvent: vi.fn() }));
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("reconnects with backoff and increments reconnectCount on close, per the no-backfill contract", () => {
    const { result } = renderHook(() => useGatewayStream("session-1", "gw-token", { onEvent: vi.fn() }));
    expect(result.current.reconnectCount).toBe(0);

    act(() => {
      FakeWebSocket.instances[0].close();
    });
    expect(result.current.reconnectCount).toBe(1);
    expect(FakeWebSocket.instances).toHaveLength(1); // reconnect is scheduled, not immediate

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("delivers parsed events to onEvent", () => {
    const onEvent = vi.fn();
    renderHook(() => useGatewayStream("session-1", "gw-token", { onEvent }));
    const socket = FakeWebSocket.instances[0];
    const event = { event_id: "e1", sensor_role: "thigh", signal_quality: { level: "HIGH" } };

    socket.onmessage?.({ data: JSON.stringify(event) });

    expect(onEvent).toHaveBeenCalledWith(event);
  });

  it("closes the socket and stops reconnecting on unmount", () => {
    const { unmount } = renderHook(() => useGatewayStream("session-1", "gw-token", { onEvent: vi.fn() }));
    const socket = FakeWebSocket.instances[0];

    unmount();

    expect(socket.closed).toBe(true);
    vi.advanceTimersByTime(20000);
    expect(FakeWebSocket.instances).toHaveLength(1); // no reconnect after unmount
  });
});
