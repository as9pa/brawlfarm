/** The shared event stream: one connection for the whole panel, per-kind handlers, a
 * backoff we control rather than the browser's, and a reconnect signal the query cache
 * refetches on. */
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  closeEvents,
  lastEventId,
  onReconnect,
  setEventSourceFactory,
  subscribe,
  useConnection,
} from "./useEvents";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  private readonly listeners = new Map<string, Set<(event: Event) => void>>();

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(kind: string, listener: (event: Event) => void): void {
    const set = this.listeners.get(kind) ?? new Set<(event: Event) => void>();
    set.add(listener);
    this.listeners.set(kind, set);
  }

  removeEventListener(kind: string, listener: (event: Event) => void): void {
    this.listeners.get(kind)?.delete(listener);
  }

  close(): void {
    this.closed = true;
  }

  /** The server accepted the connection. */
  connect(): void {
    this.onopen?.();
  }

  /** One SSE frame: an id, an event name and a JSON data payload. */
  emit(kind: string, data: unknown, id: number): void {
    const event = new MessageEvent(kind, {
      data: JSON.stringify(data),
      lastEventId: String(id),
    });
    for (const listener of [...(this.listeners.get(kind) ?? [])]) listener(event);
  }

  /** The stream dropped. */
  fail(): void {
    this.onerror?.();
  }
}

function latest(): FakeEventSource {
  const source = FakeEventSource.instances.at(-1);
  if (source === undefined) throw new Error("no EventSource has been created");
  return source;
}

beforeEach(() => {
  FakeEventSource.instances = [];
  setEventSourceFactory((url) => new FakeEventSource(url) as unknown as EventSource);
});

afterEach(() => {
  closeEvents();
  setEventSourceFactory(null);
  vi.useRealTimers();
});

describe("subscribe", () => {
  it("opens one stream on /api/events and shares it between subscribers", () => {
    subscribe("instance", () => {});
    subscribe("alert", () => {});
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(latest().url).toBe("/api/events");
  });

  it("delivers each kind's payload to its own handlers", () => {
    const instances: unknown[] = [];
    const alerts: unknown[] = [];
    const feeds: unknown[] = [];
    subscribe("instance", (data) => instances.push(data));
    subscribe("alert", (data) => alerts.push(data));
    subscribe("feed", (data) => feeds.push(data));
    latest().connect();
    latest().emit("instance", { name: "Pie64", state: "farming" }, 1);
    latest().emit("alert", { id: 4, kind: "crash" }, 2);
    latest().emit("feed", { instance: "Pie64", session: "s.jsonl", record: { seq: 9 } }, 3);
    latest().emit("log", { message: "ignored" }, 4);
    expect(instances).toEqual([{ name: "Pie64", state: "farming" }]);
    expect(alerts).toEqual([{ id: 4, kind: "crash" }]);
    expect(feeds).toEqual([{ instance: "Pie64", session: "s.jsonl", record: { seq: 9 } }]);
  });

  it("ignores a frame whose id it has already delivered", () => {
    const seen: unknown[] = [];
    subscribe("alert", (data) => seen.push(data));
    latest().connect();
    latest().emit("alert", { id: 1 }, 7);
    latest().emit("alert", { id: 1 }, 7);
    latest().emit("alert", { id: 2 }, 8);
    expect(seen).toEqual([{ id: 1 }, { id: 2 }]);
    expect(lastEventId()).toBe(8);
  });

  it("stops delivering after the returned unsubscribe runs", () => {
    const seen: unknown[] = [];
    const off = subscribe("alert", (data) => seen.push(data));
    latest().connect();
    latest().emit("alert", { id: 1 }, 1);
    off();
    latest().emit("alert", { id: 2 }, 2);
    expect(seen).toEqual([{ id: 1 }]);
  });
});

describe("useConnection", () => {
  it("reports connecting, then live, then reconnecting", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useConnection());
    act(() => {
      subscribe("instance", () => {});
    });
    expect(result.current).toBe("connecting");
    act(() => latest().connect());
    expect(result.current).toBe("live");
    act(() => latest().fail());
    expect(result.current).toBe("reconnecting");
    act(() => {
      vi.advanceTimersByTime(1000);
      latest().connect();
    });
    expect(result.current).toBe("live");
  });
});

describe("the backoff", () => {
  it("reopens after 1, 2, 4, 8, 16 then 30 seconds and stays at 30", () => {
    vi.useFakeTimers();
    subscribe("instance", () => {});
    latest().connect();
    for (const delay of [1000, 2000, 4000, 8000, 16000, 30000, 30000]) {
      const before = FakeEventSource.instances.length;
      latest().fail();
      expect(latest().closed).toBe(true);
      expect(FakeEventSource.instances).toHaveLength(before);
      vi.advanceTimersByTime(delay - 1);
      expect(FakeEventSource.instances).toHaveLength(before);
      vi.advanceTimersByTime(1);
      expect(FakeEventSource.instances).toHaveLength(before + 1);
      expect(latest().url).toBe("/api/events");
    }
  });

  it("restarts the backoff once the stream comes back", () => {
    vi.useFakeTimers();
    subscribe("instance", () => {});
    latest().connect();
    latest().fail();
    vi.advanceTimersByTime(1000);
    latest().connect();
    const before = FakeEventSource.instances.length;
    latest().fail();
    vi.advanceTimersByTime(1000);
    expect(FakeEventSource.instances).toHaveLength(before + 1);
  });
});

describe("onReconnect", () => {
  it("runs only after a stream that had already dropped comes back", () => {
    vi.useFakeTimers();
    const refetch = vi.fn();
    onReconnect(refetch);
    subscribe("instance", () => {});
    latest().connect();
    expect(refetch).not.toHaveBeenCalled();
    latest().fail();
    vi.advanceTimersByTime(1000);
    latest().connect();
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
