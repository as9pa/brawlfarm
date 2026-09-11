/**
 * A fetch stub for the tests. Every test that touches the API installs one route
 * function and gets back the calls it received, so assertions can pin the URL, the
 * method and the body the client actually sent.
 */
import { vi } from "vitest";

export type Route = (url: string, init: RequestInit | undefined) => Response | Promise<Response>;

export interface FetchCall {
  url: string;
  init: RequestInit | undefined;
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** A four-byte PNG header: enough for Response.blob(), nothing decodes it. */
export function pngResponse(): Response {
  return new Response(new Uint8Array([137, 80, 78, 71]), {
    status: 200,
    headers: { "content-type": "image/png" },
  });
}

export function stubFetch(route: Route): { calls: FetchCall[]; mock: ReturnType<typeof vi.fn> } {
  const calls: FetchCall[] = [];
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : String(input);
    calls.push({ url, init });
    return route(url, init);
  });
  vi.stubGlobal("fetch", mock);
  return { calls, mock };
}
