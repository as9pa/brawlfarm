/** The one HTTP door: what it parses, and the sentence every failure mode turns into. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, validationLines } from "./client";
import { jsonResponse, stubFetch } from "../test/http";

afterEach(() => {
  // stubFetch installs a global; leaving it behind would leak into the next file.
  vi.unstubAllGlobals();
});

describe("api", () => {
  it("returns the parsed body", async () => {
    stubFetch(() => jsonResponse({ instances: [] }));
    await expect(api<{ instances: unknown[] }>("/api/instances")).resolves.toEqual({
      instances: [],
    });
  });

  it("sends a JSON content type only when there is a body", async () => {
    const { calls } = stubFetch(() => jsonResponse({ ok: true }));
    await api("/api/instances/Pie64/stop", { method: "POST" });
    await api("/api/instances/Pie64/start", { method: "POST", body: '{"hours":2}' });
    expect(calls[0].init).toEqual({ method: "POST" });
    expect(calls[1].init).toEqual({
      method: "POST",
      body: '{"hours":2}',
      headers: { "content-type": "application/json" },
    });
  });

  it("resolves a 204 as undefined", async () => {
    stubFetch(() => new Response(null, { status: 204 }));
    await expect(api<void>("/api/alerts/1/dismiss", { method: "POST" })).resolves.toBeUndefined();
  });

  it("turns a string detail into the error detail", async () => {
    stubFetch(() => jsonResponse({ detail: "unknown instance" }, 404));
    const error = await api("/api/instances/ghost/plan").catch((failure: unknown) => failure);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, detail: "unknown instance", lines: [] });
  });

  it("turns FastAPI's validation list into lines", async () => {
    stubFetch(() =>
      jsonResponse(
        {
          detail: [
            { loc: ["body", "goal_trophies"], msg: "Input should be greater than or equal to 0" },
            { loc: ["query", "limit"], msg: "Input should be less than or equal to 1000" },
          ],
        },
        422,
      ),
    );
    const error = await api("/api/instances/Pie64/plan", { method: "PUT", body: "{}" }).catch(
      (failure: unknown) => failure,
    );
    expect(error).toMatchObject({
      status: 422,
      detail: "Some values were not accepted. Fix the fields listed and try again.",
      lines: [
        "body.goal_trophies: Input should be greater than or equal to 0",
        "query.limit: Input should be less than or equal to 1000",
      ],
    });
  });

  // One sentence per status the API answers with, each ending in the next step the
  // reader can take, plus the generic for a status the map does not name.
  const STATUS_SENTENCES: readonly [number, string][] = [
    [400, "That request was not valid. Check the values and try again."],
    [401, "The panel is not signed in to brawlfarm. Check the API token in Settings."],
    [403, "The panel is not allowed to do that. Check the API token in Settings."],
    [404, "That is not there any more. Refresh the page."],
    [409, "Something changed while you were editing. Refresh and try again."],
    [422, "Some values were not accepted. Fix the fields listed and try again."],
    [500, "brawlfarm hit an internal error. Check the panel log, then try again."],
    [503, "brawlfarm is not ready yet. Wait a moment and try again."],
  ];

  it.each(STATUS_SENTENCES)("says what to do next about a %i", async (status, detail) => {
    stubFetch(() => jsonResponse({ oops: true }, status));
    const error = await api("/api/stats").catch((failure: unknown) => failure);
    expect(error).toMatchObject({ status, detail });
  });

  it("falls back to the status when the body carries no detail", async () => {
    stubFetch(() => jsonResponse({ oops: true }, 418));
    const error = await api("/api/stats").catch((failure: unknown) => failure);
    expect(error).toMatchObject({
      status: 418,
      detail:
        "Something went wrong (HTTP 418). Try again, and check the panel log if it keeps failing.",
    });
  });

  it("turns an unreachable server into the panel's own sentence", async () => {
    stubFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    const error = await api("/api/instances").catch((failure: unknown) => failure);
    expect(error).toMatchObject({
      status: 0,
      detail: "The panel cannot reach brawlfarm. Is it still running?",
    });
  });
});

describe("validationLines", () => {
  it("joins loc with dots and ignores anything that is not an item", () => {
    expect(validationLines([{ loc: ["body", 0, "name"], msg: "required" }, "junk"])).toEqual([
      "body.0.name: required",
    ]);
    expect(validationLines("unknown instance")).toEqual([]);
  });
});
