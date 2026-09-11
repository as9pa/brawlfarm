/**
 * The top bar: where you are, whether the panel is hearing from the server, and how many
 * alerts are waiting. The connection pill is the only place the SSE state surfaces, so
 * "Reconnecting" there is the panel admitting it may be showing stale data.
 */
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useLocation } from "react-router";

import { listAlerts } from "../api/alerts";
import { queryKeys } from "../api/queries";
import { Button } from "../components/ui/Button";
import { type Connection, useConnection } from "../live/useEvents";
import { openAlertsDrawer } from "../lib/alertsDrawer";
import { TONE_DOT, type Tone } from "../lib/states";

const SECTION_TITLES: Record<string, string> = {
  "/": "Fleet",
  "/stats": "Stats",
  "/settings": "Settings",
};

const INSTANCE_PREFIX = "/instances/";

const CONNECTION_PILL: Record<Connection, { label: string; tone: Tone }> = {
  live: { label: "Live", tone: "ok" },
  reconnecting: { label: "Reconnecting", tone: "warn" },
  connecting: { label: "Connecting", tone: "idle" },
};

export function pageTitle(pathname: string): string {
  if (pathname.startsWith(INSTANCE_PREFIX)) return pathname.slice(INSTANCE_PREFIX.length);
  return SECTION_TITLES[pathname] ?? "brawlfarm";
}

export function TopBar() {
  const { pathname } = useLocation();
  const connection = useConnection();
  const { data: alerts } = useQuery({ queryKey: queryKeys.alerts(), queryFn: listAlerts });
  const unread = alerts?.unread ?? 0;
  const pill = CONNECTION_PILL[connection];

  return (
    <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-line bg-panel px-4">
      <h1 className="flex-1 truncate text-[20px] font-semibold tracking-tight">
        {pageTitle(pathname)}
      </h1>

      <span
        data-tone={pill.tone}
        className="inline-flex items-center gap-1.5 rounded-[6px] border border-line bg-panel-2 px-2 py-0.5 text-[11px] text-muted"
      >
        <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${TONE_DOT[pill.tone]}`} />
        {pill.label}
      </span>

      <Button variant="quiet" size="sm" onClick={openAlertsDrawer}>
        <Bell size={16} strokeWidth={1.6} aria-hidden="true" />
        Alerts
        {unread > 0 && (
          <span className="ml-1 rounded-[6px] bg-accent px-1.5 font-mono text-[11px] tabular-nums text-accent-ink">
            {unread}
          </span>
        )}
      </Button>
    </header>
  );
}
