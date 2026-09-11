/**
 * The alerts drawer.
 *
 * Reads the same ["alerts"] query the top bar's badge does, so dismissing a row updates
 * both. Dismissing is a plain call plus an invalidation rather than an optimistic write:
 * the list is short, the call is local, and a wrong guess here would hide an alert that
 * is still live.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { dismissAlert, dismissAllAlerts, listAlerts } from "../api/alerts";
import { queryKeys } from "../api/queries";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { Drawer } from "../components/ui/Drawer";
import { closeAlertsDrawer, useAlertsDrawerOpen } from "../lib/alertsDrawer";
import { alertKindLabel, alertKindTone } from "../lib/states";
import { hhmm } from "../lib/time";
import { failureMessage, toast } from "../lib/toast";

export function AlertsDrawer() {
  const open = useAlertsDrawerOpen();
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: queryKeys.alerts(), queryFn: listAlerts });
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
    void dismissAllAlerts()
      .then(() => {
        refresh();
        toast("Alerts dismissed");
      })
      .catch(failed);
  };

  return (
    <Drawer
      open={open}
      onClose={closeAlertsDrawer}
      title="Alerts"
      actions={
        alerts.length > 0 ? (
          <Button variant="text" size="sm" onClick={onDismissAll}>
            Dismiss all
          </Button>
        ) : undefined
      }
    >
      {alerts.length === 0 ? (
        <p className="p-4 text-[13px] text-muted">
          No alerts. Offline instances, crashes and wrong-mode recoveries show up here.
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {alerts.map((alert) => (
            <li key={alert.id} className="flex flex-col gap-1 p-3">
              <div className="flex items-center gap-2">
                <Chip tone={alertKindTone(alert.kind)}>{alertKindLabel(alert.kind)}</Chip>
                <span className="font-mono text-[12px] text-text">{alert.instance}</span>
                <span className="flex-1 text-right font-mono text-[11px] tabular-nums text-muted">
                  {hhmm(alert.ts)}
                </span>
              </div>
              <p className="text-[13px] text-muted">{alert.detail}</p>
              <div>
                <Button variant="text" size="sm" onClick={() => onDismiss(alert.id)}>
                  Dismiss
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
