/**
 * The live preview box.
 *
 * Owns its own fetch loop instead of going through react-query: the body is a Blob, not
 * JSON, and every caller wants a different cadence (a Fleet card idles, the Instance page
 * refreshes once a second, both stop when the tab is hidden). Each frame becomes an object
 * URL, and the previous one is revoked the moment it is replaced -- an unrevoked blob is
 * a megabyte of retained memory per frame.
 *
 * Polling that fast is only free because most polls change nothing: the box remembers the
 * ETag it is showing, hands it back on the next request, and a "no change" answer leaves
 * the image element exactly as it is. The caption ages from the frame's own timestamp, so
 * a frame that stays on screen for four seconds is honest about being four seconds old.
 *
 * A change of `refreshKey` fetches immediately: that is the Instance page's Refresh
 * button. The `<img>` carries data-private so the pull request's screenshots can blur it.
 */
import { type ReactNode, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { fetchPreview } from "../../api/screens";
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
  // The ETag of the frame on screen, tied to the instance it came from: a Thumb that is
  // handed a new name must not claim to already hold that instance's frame.
  const seenRef = useRef<{ name: string; etag: string | null }>({ name, etag: null });

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
        const seen = seenRef.current;
        const frame = await fetchPreview(name, seen.name === name ? seen.etag : null);
        if (cancelled) return;
        // null is "the frame you are showing is still the current one": leave the image
        // alone, so the browser has nothing to decode and nothing to repaint.
        if (frame !== null) {
          if (urlRef.current !== null) URL.revokeObjectURL(urlRef.current);
          urlRef.current = URL.createObjectURL(frame.blob);
          seenRef.current = { name, etag: frame.etag };
          setUrl(urlRef.current);
          setTakenAt(frame.takenAt);
        }
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
      {/* One stack, not two overlays: a broken adb and a scheduled break happen together
       * all the time, and centering both on inset-0 drew the caption over the error. */}
      {(error !== null || caption !== undefined) && (
        <div
          data-testid="thumb-overlay"
          className="absolute inset-0 flex flex-col items-center justify-center gap-1 p-3 text-center"
        >
          {error !== null && (
            <>
              <span className="text-[13px] text-bad">
                No screenshot yet. Check that the instance is running.
              </span>
              <span className="text-[12px] text-muted">Retrying in 15 s.</span>
            </>
          )}
          {caption !== undefined && <span className="text-[13px] text-text">{caption}</span>}
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
