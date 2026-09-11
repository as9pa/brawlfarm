/**
 * The refetch interval a query should use, or false while the tab is hidden.
 *
 * Feeds react-query's refetchInterval. A backgrounded panel must not keep asking for
 * screenshots: every one of those is an adb screencap against a live BlueStacks window.
 */
import { useEffect, useState } from "react";

export function useVisiblePolling(intervalMs: number): number | false {
  const [visible, setVisible] = useState(() => document.visibilityState === "visible");

  useEffect(() => {
    const onChange = () => {
      setVisible(document.visibilityState === "visible");
    };
    document.addEventListener("visibilitychange", onChange);
    return () => {
      document.removeEventListener("visibilitychange", onChange);
    };
  }, []);

  return visible ? intervalMs : false;
}
