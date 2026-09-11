/**
 * The live screenshot box.
 *
 * Owns its own fetch loop instead of going through react-query: the body is a Blob, not
 * JSON, and every caller wants a different cadence (a Fleet card idles, the Instance page
 * refreshes every 15 s, both stop when the tab is hidden). Each frame becomes an object
 * URL, and the previous one is revoked the moment it is replaced -- an unrevoked blob is
 * a megabyte of retained memory per frame.
 *
 * A change of `refreshKey` fetches immediately: that is the Instance page's Refresh
 * button. The `<img>` carries data-private so the pull request's screenshots can blur it.
 */
import { type ReactNode, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { fetchScreenshot } from "../../api/screens";
import { age } from "../../lib/time";

const ERROR_RETRY_MS = 15000;
const AGE_TICK_MS = 1000;

export interface ThumbProps {
  name: string;
  refreshMs: number | false;
  dimmed?: boolean;
  caption?: string;
  overlay?: ReactNode;
  refreshKey?: number;
}

export function Thumb({
  name,
  refreshMs,
  dimmed = false,
  caption,
  overlay,
  refreshKey = 0,
}: ThumbProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [takenAt, setTakenAt] = useState<number | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const schedule = (delay: number | false) => {
      if (delay === false || cancelled) return;
      timer = setTimeout(() => {
        void load();
      }, delay);
    };

    const load = async (): Promise<void> => {
      try {
        const blob = await fetchScreenshot(name);
        if (cancelled) return;
        if (urlRef.current !== null) URL.revokeObjectURL(urlRef.current);
        urlRef.current = URL.createObjectURL(blob);
        setUrl(urlRef.current);
        setTakenAt(Date.now());
        setNow(Date.now());
        setError(null);
        schedule(refreshMs);
      } catch (failure) {
        if (cancelled) return;
        setError(failure instanceof ApiError ? failure : new ApiError(0, String(failure)));
        schedule(ERROR_RETRY_MS);
      }
    };

    void load();
    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
    };
  }, [name, refreshMs, refreshKey]);

  // Revoking belongs to unmount alone: the effect above re-runs on every prop change and
  // must not throw away the frame it is about to keep showing.
  useEffect(
    () => () => {
      if (urlRef.current !== null) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
      }
    },
    [],
  );

  useEffect(() => {
    if (takenAt === null) return;
    const tick = setInterval(() => setNow(Date.now()), AGE_TICK_MS);
    return () => clearInterval(tick);
  }, [takenAt]);

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-[6px] border border-line bg-panel-2">
      {url !== null && (
        <img
          src={url}
          alt={`${name} screen`}
          data-private=""
          className={`h-full w-full object-cover transition-opacity duration-[120ms] ${dimmed ? "opacity-40" : ""}`}
        />
      )}
      {error !== null && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 p-3 text-center">
          <span className="text-[13px] text-bad">{`Screenshot failed: ${error.detail}`}</span>
          <span className="text-[12px] text-muted">Retrying in 15 s.</span>
        </div>
      )}
      {caption !== undefined && (
        <div className="absolute inset-0 flex items-center justify-center text-[13px] text-text">
          {caption}
        </div>
      )}
      {overlay !== undefined && <div className="absolute left-2 top-2">{overlay}</div>}
      {takenAt !== null && error === null && (
        <span className="absolute right-2 top-2 font-mono text-[11px] tabular-nums text-muted">
          {age(takenAt, now)}
        </span>
      )}
    </div>
  );
}
