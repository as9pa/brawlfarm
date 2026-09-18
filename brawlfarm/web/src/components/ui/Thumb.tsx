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
 * the image element exactly as it is. Nothing is drawn over the image: the frame's own
 * timestamp goes up to the caller through `onFrame`, and the caller says how old the
 * picture is in its own words, beside everything else it has to say. A caller with
 * nothing else to say asks for `showClock` instead and gets that stamp in the caption.
 *
 * A change of `refreshKey` fetches immediately: that is the Instance page's Refresh
 * button. The `<img>` carries data-private so the pull request's screenshots can blur it.
 */
import { type ReactNode, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { fetchPreview } from "../../api/screens";
import { clock } from "../../lib/format";
import { age } from "../../lib/time";

const ERROR_RETRY_MS = 15000;

export interface ThumbProps {
  name: string;
  refreshMs: number | false;
  dimmed?: boolean;
  caption?: string;
  overlay?: ReactNode;
  refreshKey?: number;
  /** The millisecond stamp of each new frame, for a caller that shows its age. */
  onFrame?: (takenAt: number) => void;
  /** True while a capture the caller asked for is in flight, so it can say so on its own
   * controls. The interval poll stays quiet: a control that went dead once a second would
   * flicker rather than inform. */
  onBusyChange?: (busy: boolean) => void;
  /** Caption the frame with its age and the time it was taken, rather than nothing. */
  showClock?: boolean;
}

export function Thumb({
  name,
  refreshMs,
  dimmed = false,
  caption,
  overlay,
  refreshKey = 0,
  onFrame,
  onBusyChange,
  showClock = false,
}: ThumbProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  // Both halves of the stamp are taken when the frame arrives, the way a Fleet card takes
  // them: a 304 changes neither, and nothing else rerenders the box.
  const [stamp, setStamp] = useState<{ takenAt: number; seenAt: number } | null>(null);
  const urlRef = useRef<string | null>(null);
  // Read through a ref rather than listed as a dependency: a caller that writes the
  // handler inline hands over a new function on every render, and the fetch loop below
  // would restart on each one.
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;
  const onBusyChangeRef = useRef(onBusyChange);
  onBusyChangeRef.current = onBusyChange;
  // Only a change goes up. A caller keeps this in state, and a repeat of the value it
  // already holds would rerender it for nothing.
  const busyRef = useRef(false);
  // The refreshKey the box has already fetched for: a different one means a press, which
  // is the only load that announces itself.
  const pressedRef = useRef(refreshKey);
  // The ETag of the frame on screen, tied to the instance it came from: a Thumb that is
  // handed a new name must not claim to already hold that instance's frame.
  const seenRef = useRef<{ name: string; etag: string | null }>({ name, etag: null });

  // Declared before the fetch effect so that on unmount its cleanup runs first, and the
  // fetch effect's cleanup can tell a teardown from a plain re-run.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    // Only the first load of a run the press started speaks; every poll it schedules
    // afterwards is background again.
    const pressed = refreshKey !== pressedRef.current;
    pressedRef.current = refreshKey;
    let first = true;
    let announced = false;

    const schedule = (delay: number | false) => {
      if (delay === false || cancelled) return;
      timer = setTimeout(() => {
        void load();
      }, delay);
    };

    // Never on a render path and never after unmount: this drives a caller's setState,
    // and either one would loop.
    const report = (busy: boolean) => {
      if (busyRef.current === busy) return;
      busyRef.current = busy;
      onBusyChangeRef.current?.(busy);
    };

    const load = async (): Promise<void> => {
      const speaks = pressed && first;
      first = false;
      if (speaks) {
        announced = true;
        report(true);
      }
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
          setStamp({ takenAt: frame.takenAt, seenAt: Date.now() });
          onFrameRef.current?.(frame.takenAt);
        }
        setError(null);
        if (speaks) report(false);
        schedule(refreshMs);
      } catch (failure) {
        if (cancelled) return;
        setError(failure instanceof ApiError ? failure : new ApiError(0, String(failure)));
        if (speaks) report(false);
        schedule(ERROR_RETRY_MS);
      }
    };

    void load();
    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
      // A pressed capture thrown away by a prop change never settles, so the control it
      // disabled is freed here instead. On unmount there is no control left to free.
      if (announced && mountedRef.current) report(false);
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

  // clock() reads an ISO string, and a frame's stamp is milliseconds, so it is converted
  // here rather than twice below.
  const takenAtIso = stamp === null ? null : new Date(stamp.takenAt).toISOString();
  const takenAtClock = takenAtIso === null ? undefined : clock(takenAtIso);
  // The stamp speaks for the caption: the page that asks for the clock never captions a
  // break, and a break card never asks for the clock.
  const shownCaption =
    showClock && stamp !== null
      ? `${age(stamp.takenAt, stamp.seenAt)} (${takenAtClock})`
      : caption;

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
      {(error !== null || shownCaption !== undefined) && (
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
          {shownCaption !== undefined && (
            <span className="text-[13px] text-text" title={takenAtClock}>
              {shownCaption}
            </span>
          )}
        </div>
      )}
      {overlay !== undefined && <div className="absolute left-2 top-2">{overlay}</div>}
    </div>
  );
}
