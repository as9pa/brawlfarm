/**
 * The alerts drawer.
 *
 * Reads the same ["alerts"] query the top bar's badge does, so dismissing a row updates
 * both. Dismissing is a plain call plus an invalidation rather than an optimistic write:
 * the list is short, the call is local, and a wrong guess here would hide an alert that
 * is still live.
 *
 * Rows say how long ago rather than at what time, with the dated stamp in a title: an
 * alert can still be on screen the morning after it fired, and "19:42" alone does not say
 * which evening that was. The day headings do the rest.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { dismissAlert, dismissAllAlerts, listAlerts } from "../api/alerts";
import { queryKeys } from "../api/queries";
import type { Alert } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { Drawer } from "../components/ui/Drawer";
import { closeAlertsDrawer, useAlertsDrawerOpen } from "../lib/alertsDrawer";
import { dateTime, num } from "../lib/format";
import { alertKindLabel, alertKindTone } from "../lib/states";
import { since } from "../lib/time";
import { failureMessage, toast } from "../lib/toast";

/** Three bones the width of a row. aria-hidden because a screen reader has nothing to read
 * here yet, and the rows that arrive are what it should announce. */
function Skeleton() {
  return (
    <ul data-testid="alerts-skeleton" className="divide-y divide-line">
      {[0, 1, 2].map((i) => (
        <li
          key={i}
          aria-hidden="true"
          className="flex animate-pulse flex-col gap-2 p-3"
        >
          <div
            data-block=""
            className="h-[18px] w-[180px] rounded-[4px] bg-panel-2"
          />
          <div
            data-block=""
            className="h-[14px] w-full rounded-[4px] bg-panel-2"
          />
        </li>
      ))}
    </ul>
  );
}

export function AlertsDrawer() {
  const open = useAlertsDrawerOpen();
  const client = useQueryClient();
  const { data, isPending } = useQuery({
    queryKey: queryKeys.alerts(),
    queryFn: listAlerts,
  });
  const [confirming, setConfirming] = useState(false);
  const alerts = data?.alerts ?? [];

  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.alerts() });
  };

  /** A refusal speaks the API's own sentence rather than disappearing into an unhandled
   * promise. The rows are left alone either way: the list is only ever redrawn by a
   * refetch, so an alert that is still live stays readable. */
  const failed = (failure: unknown) => {
    toast(failureMessage(failure));
  };

  const onDismiss = (id: number) => {
    void dismissAlert(id).then(refresh).catch(failed);
  };

  const onDismissAll = () => {
    setConfirming(false);
    void dismissAllAlerts()
      .then(() => {
        refresh();
        toast("Alerts dismissed");
      })
      .catch(failed);
  };

  const now = Date.now();
  // The calendar day, not a span of hours: an alert from 23:50 last night is yesterday's
  // at 00:10 this morning, however few minutes ago it fired.
  const today = new Date(now).toDateString();
  const groups: { label: string; rows: Alert[] }[] = [
    {
      label: "Today",
      rows: alerts.filter(
        (alert) => new Date(alert.ts).toDateString() === today,
      ),
    },
    {
      label: "Earlier",
      rows: alerts.filter(
        (alert) => new Date(alert.ts).toDateString() !== today,
      ),
    },
  ];

  const list = groups
    .filter((group) => group.rows.length > 0)
    .map((group) => (
      <section key={group.label}>
        <h3 className="px-3 pt-3 text-[11px] uppercase tracking-wide text-muted">
          {group.label}
        </h3>
        <ul className="divide-y divide-line">
          {group.rows.map((alert) => (
            <li key={alert.id} className="flex flex-col gap-1 p-3">
              <div className="flex items-center gap-2">
                <Chip tone={alertKindTone(alert.kind)}>
                  {alertKindLabel(alert.kind)}
                </Chip>
                <span className="font-mono text-[12px] text-text">
                  {alert.instance}
                </span>
                <span
                  title={dateTime(alert.ts)}
                  className="flex-1 text-right font-mono text-[11px] tabular-nums text-muted"
                >
                  {since(Date.parse(alert.ts), now)}
                </span>
              </div>
              <p className="text-[13px] text-muted">{alert.detail}</p>
              <div>
                <Button
                  variant="quiet"
                  size="sm"
                  onClick={() => onDismiss(alert.id)}
                >
                  Dismiss
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    ));

  return (
    <>
      <Drawer
        open={open}
        onClose={closeAlertsDrawer}
        title={alerts.length > 0 ? `Alerts, ${num(alerts.length)}` : "Alerts"}
        actions={
          alerts.length > 0 ? (
            <Button
              variant="quiet"
              size="sm"
              onClick={() => setConfirming(true)}
            >
              Dismiss all
            </Button>
          ) : undefined
        }
      >
        {isPending ? (
          <Skeleton />
        ) : alerts.length === 0 ? (
          <p className="p-4 text-[13px] text-muted">
            No alerts. Offline instances, crashes and wrong-mode recoveries show
            up here.
          </p>
        ) : (
          list
        )}
      </Drawer>
      {/* A sibling of the drawer rather than a child: its own panel sits above the drawer's
          and owns the focus while it is up. */}
      <ConfirmDialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Dismiss all alerts?"
        body="They leave the drawer and the bell count. Nothing is un-dismissed."
        confirmLabel="Dismiss all"
        tone="bad"
        onConfirm={onDismissAll}
      />
    </>
  );
}
