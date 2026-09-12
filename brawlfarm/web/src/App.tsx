/**
 * The panel's root.
 *
 * Providers, routes, and the two effects that make the whole thing live: the theme
 * bootstrap (one read of GET /api/settings, from which only app.theme is used) and the
 * event-stream handlers. `instance` and `alert` live here rather than in the screens so
 * a page that is not mounted still keeps its cache warm, and so there is exactly one
 * subscriber for each. `feed` is not one of them: a feed record only matters to the
 * screen that is showing that instance's feed, so the Feed component subscribes itself
 * (task 9) and this file stays out of it.
 */
import { QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { Shell } from "./app/Shell";
import { Calibration } from "./calibration/Calibration";
import { createQueryClient, queryKeys } from "./api/queries";
import { getSettings } from "./api/settings";
import { Toaster } from "./components/ui/Toast";
import { Fleet } from "./fleet/Fleet";
import { Instance } from "./instance/Instance";
import { onReconnect, subscribe } from "./live/useEvents";
import { Settings } from "./settings/Settings";
import { Setup } from "./setup/Setup";
import { Stats } from "./stats/Stats";

/** A burst of state changes (a tick touching five instances) is one refetch, not five. */
const INSTANCE_DEBOUNCE_MS = 250;

function useThemeBootstrap(): void {
  const { data } = useQuery({ queryKey: queryKeys.settings(), queryFn: getSettings });
  const theme = data?.app.theme;

  useEffect(() => {
    if (theme === undefined) return;
    if (theme === "system") {
      delete document.documentElement.dataset.theme;
    } else {
      document.documentElement.dataset.theme = theme;
    }
  }, [theme]);
}

function useLiveHandlers(): void {
  const client = useQueryClient();

  useEffect(() => {
    let pending: ReturnType<typeof setTimeout> | null = null;

    const offInstance = subscribe("instance", () => {
      if (pending !== null) return;
      pending = setTimeout(() => {
        pending = null;
        void client.invalidateQueries({ queryKey: queryKeys.instances() });
      }, INSTANCE_DEBOUNCE_MS);
    });

    const offAlert = subscribe("alert", () => {
      void client.invalidateQueries({ queryKey: queryKeys.alerts() });
    });

    // The API only replays from the browser's own Last-Event-ID header, which our manual
    // reopen never sends, so a reconnect refetches instead of catching up.
    const offReconnect = onReconnect(() => {
      void client.invalidateQueries({ queryKey: queryKeys.instances() });
      void client.invalidateQueries({ queryKey: queryKeys.alerts() });
      void client.invalidateQueries({ queryKey: ["feed"] });
    });

    return () => {
      if (pending !== null) clearTimeout(pending);
      offInstance();
      offAlert();
      offReconnect();
    };
  }, [client]);
}

/** Everything that lives inside the shell. Task 8 puts the wizard's route beside it, which
 * is the only reason it is a component of its own rather than the body of Panel. */
function ShellRoutes() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Fleet />} />
        <Route path="/instances/:name" element={<Instance />} />
        <Route path="/stats" element={<Stats />} />
        <Route path="/calibration" element={<Calibration />} />
        <Route path="/settings" element={<Navigate to="/settings/instances" replace />} />
        <Route path="/settings/:section" element={<Settings />} />
      </Routes>
    </Shell>
  );
}

function Panel() {
  useThemeBootstrap();
  useLiveHandlers();

  // The wizard is deliberately outside ShellRoutes: it is the one page with no fleet
  // behind it, so it carries its own chrome.
  return (
    <Routes>
      <Route path="/setup" element={<Setup />} />
      <Route path="*" element={<ShellRoutes />} />
    </Routes>
  );
}

export function App() {
  const [client] = useState(createQueryClient);

  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <Panel />
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
