/**
 * The API's payloads as TypeScript.
 *
 * Mirrors brawlfarm/api/*.py exactly: optional in Python means `| null` here, never
 * `?`, because the API always sends the key. Anything the panel does not use (the stats
 * series, the settings sections other than app.theme) is left out on purpose -- the
 * client must not carry connection.brawl_api_token anywhere near a component.
 */

export type InstanceState =
  | "farming"
  | "stopped"
  | "scheduled_break"
  | "reconnecting"
  | "offline"
  | "starting"
  | "stopping";

export type Health = "healthy" | "stale" | "dead";

export type Phase = "at_menu" | "queuing" | "playing" | "returning";

export interface InstanceSession {
  minutes_elapsed: number | null;
  start_trophies: number | null;
  last_trophies: number | null;
  disconnect_count: number | null;
  recovery_attempts: number | null;
  session: string | null;
}

export interface Today {
  games: number;
  trophies: number;
}

export interface InstancePayload {
  name: string;
  adb_port: number;
  state: InstanceState;
  health: Health;
  pid: number | null;
  heartbeat_age_s: number | null;
  /** The worker's own phase string; unknown values are shown as they arrive. */
  phase: Phase | string | null;
  desired: "run" | "stop";
  desired_reason: string | null;
  until: string | null;
  games_played: number | null;
  farm_brawler: string | null;
  note: string;
  player_tag: string;
  session: InstanceSession | null;
  today: Today;
}

export interface InstancesResponse {
  instances: InstancePayload[];
}

export interface FarmPlan {
  mode: "ladder" | "prestige";
  prestige_start: "highest" | "lowest";
  goal_trophies: number;
  maxed_fallback: string | null;
}

export interface RosterBrawler {
  id: number;
  name: string;
  trophies: number;
  highest: number;
  rank: number;
  power: number;
}

export type RosterStatus = "ok" | "no_token" | "no_tag" | "unavailable";

export interface PlanCurrent {
  brawler: string | null;
  trophies: number | null;
  goal: number;
}

export interface PlanResponse extends FarmPlan {
  current: PlanCurrent;
  roster: RosterBrawler[] | null;
  queue: string[];
  roster_status: RosterStatus;
}

export interface ScheduleSession {
  start: string;
  end: string;
}

export interface ScheduleOverride {
  mode: "run" | "stop";
  until: string;
  set_at: string | null;
}

export interface SchedulePayload {
  enabled: boolean;
  override: ScheduleOverride | null;
  plan_date: string | null;
  sessions: ScheduleSession[];
  day_end: string | null;
  desired: Record<string, unknown> | null;
  games_played_today: number;
  now: string;
}

export interface SchedulePatch {
  enabled?: boolean;
  redraw?: boolean;
  clear_override?: boolean;
}

export type FeedCategory = "matches" | "interrupts" | "errors" | "other";

export type FeedKind = "all" | "matches" | "interrupts" | "errors";

export interface FeedRecord {
  ts: string;
  /** The line's 1-based position in the session file; unique within one session. */
  seq: number;
  event: string;
  category: FeedCategory;
  fields: Record<string, unknown>;
}

export interface FeedResponse {
  session: string | null;
  records: FeedRecord[];
}

/** The SSE "feed" payload. */
export interface FeedEvent {
  instance: string;
  session: string | null;
  record: FeedRecord;
}

export interface Alert {
  id: number;
  ts: string;
  instance: string;
  kind: string;
  title: string;
  detail: string;
  dismissed: boolean;
}

export interface AlertsResponse {
  alerts: Alert[];
  unread: number;
}

export interface StatsSummary {
  games: number;
  trophies: number;
  trophies_per_hour: number | null;
  avg_rank: number | null;
  top4_rate: number | null;
  hours_farmed: number;
}

export interface StatsResponse {
  range: string;
  instances: string[];
  summary: StatsSummary;
}

/** Only app.theme is read. The rest of GET /api/settings, including the plaintext Brawl
 * Stars token, is deliberately not modelled so no component can reach it. */
export interface AppSettings {
  app: {
    port: number;
    theme: "system" | "dark" | "light";
  };
}
