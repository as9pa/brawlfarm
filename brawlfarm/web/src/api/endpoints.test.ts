/** Every route module: the URL it builds, the method and body it sends, and the shape it
 * hands back. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { dismissAlert, dismissAllAlerts, listAlerts } from "./alerts";
import { ApiError } from "./client";
import { getFeed } from "./feed";
import { listInstances, restartInstance, retryInstance, startInstance, stopInstance } from "./instances";
import { getPlan, putPlan } from "./plans";
import { fetchPreview, screenshotUrl } from "./screens";
import { getSchedule, patchSchedule } from "./schedule";
import { getSettings } from "./settings";
import { getStatsToday } from "./stats";
import { jpegResponse, jsonResponse, stubFetch } from "../test/http";
import { makeAlert, makeInstance } from "../test/fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("instances", () => {
  it("unwraps the instances envelope", async () => {
    const { calls } = stubFetch(() => jsonResponse({ instances: [makeInstance()] }));
    const instances = await listInstances();
    expect(instances.map((inst) => inst.name)).toEqual(["Pie64"]);
    expect(calls[0].url).toBe("/api/instances");
  });

  it("posts start with hours, and with an empty body to clear a stop override", async () => {
    const { calls } = stubFetch(() => jsonResponse({ ok: true }));
    await startInstance("Pie64", 2);
    await startInstance("Pie64");
    expect(calls[0]).toEqual({
      url: "/api/instances/Pie64/start",
      init: {
        method: "POST",
        body: '{"hours":2}',
        headers: { "content-type": "application/json" },
      },
    });
    expect(calls[1].init?.body).toBe("{}");
  });

  it("posts the other three controls with no body", async () => {
    const { calls } = stubFetch(() => jsonResponse({ ok: true }));
    await stopInstance("Pie64");
    await restartInstance("Pie64");
    await retryInstance("Pie64");
    expect(calls.map((call) => call.url)).toEqual([
      "/api/instances/Pie64/stop",
      "/api/instances/Pie64/restart",
      "/api/instances/Pie64/retry",
    ]);
    expect(calls.every((call) => call.init?.body === undefined)).toBe(true);
  });
});

describe("plans and schedule", () => {
  it("reads and writes the plan", async () => {
    const { calls } = stubFetch(() =>
      jsonResponse({
        mode: "ladder",
        prestige_start: "highest",
        goal_trophies: 1000,
        maxed_fallback: null,
        quest_aware: false,
        current: { brawler: "NORI", trophies: 812, goal: 1000 },
        roster: null,
        queue: [],
        roster_status: "no_token",
      }),
    );
    const plan = await getPlan("Pie64");
    expect(plan.roster_status).toBe("no_token");
    await putPlan("Pie64", {
      mode: "prestige",
      prestige_start: "lowest",
      goal_trophies: 1000,
      maxed_fallback: null,
      quest_aware: false,
    });
    expect(calls[1]).toEqual({
      url: "/api/instances/Pie64/plan",
      init: {
        method: "PUT",
        body: '{"mode":"prestige","prestige_start":"lowest","goal_trophies":1000,"maxed_fallback":null,"quest_aware":false}',
        headers: { "content-type": "application/json" },
      },
    });
  });

  it("patches the schedule with only the keys it was given", async () => {
    const { calls } = stubFetch(() => jsonResponse({ enabled: true, sessions: [] }));
    await getSchedule("Pie64");
    await patchSchedule("Pie64", { redraw: true });
    expect(calls[0].url).toBe("/api/instances/Pie64/schedule");
    expect(calls[1].init).toEqual({
      method: "PUT",
      body: '{"redraw":true}',
      headers: { "content-type": "application/json" },
    });
  });
});

describe("feed, alerts, stats and settings", () => {
  it("asks the feed for one kind and a limit", async () => {
    const { calls } = stubFetch(() => jsonResponse({ session: null, records: [] }));
    await getFeed("Pie64", "errors", 200);
    expect(calls[0].url).toBe("/api/instances/Pie64/feed?kind=errors&limit=200");
  });

  it("lists, dismisses one and dismisses all alerts", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: [makeAlert()], unread: 1 })
        : new Response(null, { status: 204 }),
    );
    const body = await listAlerts();
    expect(body.unread).toBe(1);
    await expect(dismissAlert(1)).resolves.toBeUndefined();
    await expect(dismissAllAlerts()).resolves.toBeUndefined();
    expect(calls.map((call) => call.url)).toEqual([
      "/api/alerts",
      "/api/alerts/1/dismiss",
      "/api/alerts/dismiss-all",
    ]);
  });

  it("scopes today's stats to one instance when asked", async () => {
    const { calls } = stubFetch(() =>
      jsonResponse({ range: "today", instances: ["Pie64"], summary: { avg_rank: 3.4 } }),
    );
    await getStatsToday();
    await getStatsToday("Pie64");
    expect(calls.map((call) => call.url)).toEqual([
      "/api/stats?range=today",
      "/api/stats?range=today&instances=Pie64",
    ]);
  });

  it("reads only the theme out of the settings document", async () => {
    stubFetch(() =>
      jsonResponse({
        app: { port: 8765, theme: "dark" },
        connection: { adb_path: "adb.exe", brawl_api_token: "must-not-be-used" },
      }),
    );
    const settings = await getSettings();
    expect(settings.app.theme).toBe("dark");
  });
});

describe("screenshots", () => {
  it("builds the url the Full size link opens", () => {
    expect(screenshotUrl("Pie64")).toBe("/api/instances/Pie64/screenshot.png");
  });
});

describe("preview", () => {
  const LAST_MODIFIED = "Thu, 10 Sep 2026 12:00:00 GMT";

  it("fetches the frame uncached and dates it by Last-Modified", async () => {
    const { calls } = stubFetch(() =>
      jpegResponse({ etag: '"1-2"', "last-modified": LAST_MODIFIED }),
    );
    const frame = await fetchPreview("Pie64", null);
    expect(calls[0].url).toBe("/api/instances/Pie64/preview.jpg");
    expect(calls[0].init).toEqual({ cache: "no-store" });
    expect(frame?.blob.size).toBe(4);
    expect(frame?.etag).toBe('"1-2"');
    expect(frame?.takenAt).toBe(Date.parse(LAST_MODIFIED));
  });

  it("dates a frame the server did not stamp by the moment it arrived", async () => {
    stubFetch(() => jpegResponse({ etag: '"1-2"' }));
    const before = Date.now();
    const frame = await fetchPreview("Pie64", null);
    expect(frame?.takenAt).toBeGreaterThanOrEqual(before);
  });

  it("asks for the frame it already holds and reads the 304 as no change", async () => {
    const { calls } = stubFetch(() => new Response(null, { status: 304 }));
    expect(await fetchPreview("Pie64", '"1-2"')).toBeNull();
    expect(calls[0].init?.headers).toEqual({ "if-none-match": '"1-2"' });
  });

  it("reads an unchanged etag as no change even when the body came anyway", async () => {
    stubFetch(() => jpegResponse({ etag: '"1-2"' }));
    expect(await fetchPreview("Pie64", '"1-2"')).toBeNull();
  });

  it("turns a 503 into its detail", async () => {
    stubFetch(() => jsonResponse({ detail: "adb did not answer" }, 503));
    const error = await fetchPreview("Pie64", null).catch((failure: unknown) => failure);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 503, detail: "adb did not answer" });
  });
});
