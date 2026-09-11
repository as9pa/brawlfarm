/**
 * One EventSource for the whole panel.
 *
 * The browser's own auto-reconnect is not used: on an error the stream is closed and a
 * timer reopens it on a 1, 2, 4, 8, 16, 30 s backoff, so the connection pill and the
 * refetch-after-reconnect hook have something deterministic to report. The API replays
 * history only from the browser's own Last-Event-ID header, which a manual reopen never
 * sends, so a reconnect invalidates the queries instead of replaying frames.
 *
 * Module state rather than a provider: the stream must survive a route change, and every
 * screen that wants live data wants the same one connection.
 */
import { useSyncExternalStore } from "react";

export type Connection = "connecting" | "live" | "reconnecting";
export type EventKind = "instance" | "feed" | "alert" | "log";
export type EventHandler = (data: unknown) => void;
export type EventSourceFactory = (url: string) => EventSource;

export const EVENTS_URL = "/api/events";
export const BACKOFF_MS: readonly number[] = [1000, 2000, 4000, 8000, 16000, 30000];

const KINDS: readonly EventKind[] = ["instance", "feed", "alert", "log"];

const browserFactory: EventSourceFactory = (url) => new EventSource(url);

let makeSource: EventSourceFactory = browserFactory;
let source: EventSource | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let attempt = 0;
let lastId = 0;
let connection: Connection = "connecting";

const handlers = new Map<EventKind, Set<EventHandler>>();
const reconnectHandlers = new Set<() => void>();
const connectionListeners = new Set<() => void>();

/** Tests inject a fake here; null puts the browser's EventSource back. */
export function setEventSourceFactory(factory: EventSourceFactory | null): void {
  makeSource = factory ?? browserFactory;
}

/** Drop the connection and every handler. Tests call it between cases; nothing in the
 * app does, because the stream lives as long as the tab. */
export function closeEvents(): void {
  if (retryTimer !== null) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
  source?.close();
  source = null;
  attempt = 0;
  lastId = 0;
  handlers.clear();
  reconnectHandlers.clear();
  setConnection("connecting");
}

/** The id of the newest frame delivered on this connection; resets on every open. */
export function lastEventId(): number {
  return lastId;
}

export function subscribe(kind: EventKind, handler: EventHandler): () => void {
  const set = handlers.get(kind) ?? new Set<EventHandler>();
  set.add(handler);
  handlers.set(kind, set);
  openIfNeeded();
  return () => {
    set.delete(handler);
  };
}

export function onReconnect(handler: () => void): () => void {
  reconnectHandlers.add(handler);
  openIfNeeded();
  return () => {
    reconnectHandlers.delete(handler);
  };
}

export function useConnection(): Connection {
  return useSyncExternalStore(
    subscribeConnection,
    () => connection,
    () => connection,
  );
}

function subscribeConnection(listener: () => void): () => void {
  connectionListeners.add(listener);
  return () => {
    connectionListeners.delete(listener);
  };
}

/** One subscriber that throws must not cost the subscribers after it their turn: the
 * loop would abort, and for a frame dispatch has already counted in lastId there is no
 * second chance to deliver it. The panel reports the failure and carries on. */
function runSafely(what: string, handler: () => void): void {
  try {
    handler();
  } catch (error) {
    console.error(`useEvents: a ${what} handler threw`, error);
  }
}

function setConnection(next: Connection): void {
  if (connection === next) return;
  connection = next;
  for (const listener of [...connectionListeners]) runSafely("connection", listener);
}

function openIfNeeded(): void {
  if (source !== null || retryTimer !== null) return;
  open();
}

function open(): void {
  setConnection(attempt === 0 ? "connecting" : "reconnecting");
  const opened = makeSource(EVENTS_URL);
  source = opened;

  opened.onopen = () => {
    const reconnected = attempt > 0;
    attempt = 0;
    // A fresh connection starts the server's replay window over, so the id we compare
    // against has to start over too.
    lastId = 0;
    setConnection("live");
    if (reconnected) {
      for (const handler of [...reconnectHandlers]) runSafely("reconnect", handler);
    }
  };

  opened.onerror = () => {
    if (source !== opened) return; // a stale source we already replaced
    opened.close();
    source = null;
    setConnection("reconnecting");
    const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)] ?? 30000;
    attempt += 1;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      open();
    }, delay);
  };

  for (const kind of KINDS) {
    opened.addEventListener(kind, (event) => {
      dispatch(kind, event as MessageEvent<string>);
    });
  }
}

function dispatch(kind: EventKind, event: MessageEvent<string>): void {
  const id = Number(event.lastEventId);
  if (Number.isFinite(id) && id > 0) {
    if (id <= lastId) return;
    lastId = id;
  }
  let data: unknown;
  try {
    data = JSON.parse(event.data);
  } catch {
    return; // a frame we cannot parse is one frame lost, never a dead stream
  }
  for (const handler of [...(handlers.get(kind) ?? [])]) {
    runSafely(kind, () => {
      handler(data);
    });
  }
}
