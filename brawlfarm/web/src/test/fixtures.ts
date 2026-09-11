/**
 * Payload builders for the tests. Shapes match the API exactly, so a component test
 * fails the same way the real payload would. The names, ports and tag are invented:
 * Pie64 / Pie64_1 / Pie64_3 on 5555 / 5565 / 5585 with the made-up tag #2P0YLQ9, which
 * tools/scrub_check.py does not match.
 */
import type {
  Alert,
  FeedRecord,
  InstancePayload,
  PlanResponse,
  RosterBrawler,
  SchedulePayload,
} from "../api/types";

export function makeInstance(overrides: Partial<InstancePayload> = {}): InstancePayload {
  return {
    name: "Pie64",
    adb_port: 5555,
    state: "farming",
    health: "healthy",
    pid: 4242,
    heartbeat_age_s: 3.5,
    phase: "playing",
    desired: "run",
    desired_reason: "session",
    until: "2026-09-11T20:18:00",
    games_played: 12,
    farm_brawler: "NORI",
    note: "",
    player_tag: "#2P0YLQ9",
    session: {
      minutes_elapsed: 72,
      start_trophies: 41200,
      last_trophies: 41286,
      disconnect_count: 1,
      recovery_attempts: 0,
      session: "session-20260911-190540.jsonl",
    },
    today: { games: 12, trophies: 86 },
    ...overrides,
  };
}

export function makeAlert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: 1,
    ts: "2026-09-11T19:42:00",
    instance: "Pie64",
    kind: "crash",
    title: "Bot crashed",
    detail: "err=adb did not answer",
    dismissed: false,
    ...overrides,
  };
}

export function makeFeedRecord(overrides: Partial<FeedRecord> = {}): FeedRecord {
  return {
    ts: "2026-09-11T19:05:40",
    seq: 1,
    event: "phase",
    category: "matches",
    fields: { to: "playing", frm: "queuing", games: 3 },
    ...overrides,
  };
}

export function makeRosterBrawler(overrides: Partial<RosterBrawler> = {}): RosterBrawler {
  return {
    id: 16000101,
    name: "NORI",
    trophies: 812,
    highest: 830,
    rank: 25,
    power: 11,
    ...overrides,
  };
}

export function makePlan(overrides: Partial<PlanResponse> = {}): PlanResponse {
  return {
    mode: "ladder",
    prestige_start: "highest",
    goal_trophies: 1000,
    maxed_fallback: null,
    current: { brawler: "NORI", trophies: 812, goal: 1000 },
    roster: [
      makeRosterBrawler(),
      makeRosterBrawler({ id: 16000000, name: "SHELLY", trophies: 615, highest: 700, rank: 20 }),
      makeRosterBrawler({ id: 16000002, name: "TARA", trophies: 540, highest: 615, rank: 19 }),
    ],
    queue: ["TARA", "SHELLY"],
    roster_status: "ok",
    ...overrides,
  };
}

export function makeSchedule(overrides: Partial<SchedulePayload> = {}): SchedulePayload {
  return {
    enabled: true,
    override: null,
    plan_date: "2026-09-11",
    sessions: [
      { start: "2026-09-11T09:00:00", end: "2026-09-11T11:00:00" },
      { start: "2026-09-11T13:30:00", end: "2026-09-11T15:00:00" },
      { start: "2026-09-11T19:00:00", end: "2026-09-11T20:30:00" },
    ],
    day_end: "2026-09-11T20:30:00",
    desired: null,
    games_played_today: 12,
    now: "2026-09-11T14:15:00",
    ...overrides,
  };
}
