/** The instance page's activity feed: the four chips, Follow, and the live appends that
 * keep the list moving between the once-per-chip loads. */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { getFeed } from "../api/feed";
import { queryKeys } from "../api/queries";
import type { FeedEvent, FeedKind, FeedRecord, FeedResponse } from "../api/types";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Segmented } from "../components/ui/Segmented";
import { Switch } from "../components/ui/Switch";
import { feedText } from "../lib/feedText";
import { TONE_DOT } from "../lib/states";
import { hhmmss } from "../lib/time";
import { subscribe } from "../live/useEvents";

const KINDS: { value: FeedKind; label: string }[] = [
  { value: "all", label: "All" },
  { value: "matches", label: "Matches" },
  { value: "interrupts", label: "Interrupts" },
  { value: "errors", label: "Errors" },
];

const EMPTY: Record<FeedKind, string> = {
  all: "No lines yet. The feed fills as the worker plays.",
  matches: "No matches this session.",
  interrupts: "No interrupts this session.",
  errors: "No errors this session.",
};

const INITIAL_LIMIT = 200;
const FOLLOW_SLACK_PX = 40; // a nudge of the wheel is not "I want to read back"
/** A long session writes thousands of lines; the reader scrolls back a screen or two, not
 * a whole afternoon, so the list keeps the newest 500 and lets the rest go. */
const MAX_RECORDS = 500;

/** A line's identity: its 1-based seq inside the session file that produced it. */
export function feedKey(session: string | null, record: FeedRecord): string {
  return `${session ?? ""}:${record.seq}`;
}

/**
 * Append one live record. A seq already in the list is dropped, so an SSE replay after a
 * reconnect cannot double a match; a different session filename means the worker rolled
 * the file, so the list starts again from that line. The list is capped at MAX_RECORDS,
 * oldest dropped first.
 */
export function appendRecord(
  prev: FeedResponse | undefined,
  session: string | null,
  record: FeedRecord,
): FeedResponse {
  if (prev === undefined || prev.session !== session) return { session, records: [record] };
  const seen = new Set(prev.records.map((r) => feedKey(session, r)));
  if (seen.has(feedKey(session, record))) return prev;
  return { session, records: [...prev.records, record].slice(-MAX_RECORDS) };
}

/**
 * This session's narration. History comes from the API once per chip; everything after
 * that arrives on the event stream and is written into the cache for All AND for the
 * record's own chip, so switching chips never loses a line and the session panel's
 * interrupt count (task 11) stays live off the All entry without a second subscription.
 * Only a chip that has already loaded is written to, though: see the stream handler.
 */
export function Feed({ name, session }: { name: string; session: string | null }) {
  const client = useQueryClient();
  const [kind, setKind] = useState<FeedKind>("all");
  const [follow, setFollow] = useState(true);
  const listRef = useRef<HTMLDivElement | null>(null);

  const query = useQuery({
    queryKey: queryKeys.feed(name, kind),
    queryFn: () => getFeed(name, kind, INITIAL_LIMIT),
  });

  useEffect(
    () =>
      subscribe("feed", (payload: unknown) => {
        const event = payload as FeedEvent;
        if (event.instance !== name) return;
        // "other" has no chip of its own, so those lines land under All alone.
        const targets: FeedKind[] =
          event.record.category === "other" ? ["all"] : ["all", event.record.category];
        for (const target of targets) {
          const key = queryKeys.feed(name, target);
          // A chip nobody has opened is left alone. Seeding it here would leave a
          // one-line list that setQueryData keeps marking fresh on every append, so the
          // chip would never fetch its own history; that fetch carries this record anyway.
          if (client.getQueryData(key) === undefined) continue;
          client.setQueryData<FeedResponse>(key, (prev) =>
            appendRecord(prev, event.session, event.record),
          );
        }
      }),
    [client, name],
  );

  const records = query.data?.records ?? [];
  const active = query.data?.session ?? session;

  useEffect(() => {
    const el = listRef.current;
    if (el !== null && follow) el.scrollTop = el.scrollHeight;
  }, [records.length, follow, kind]);

  const onScroll = () => {
    const el = listRef.current;
    if (el === null || !follow) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight > FOLLOW_SLACK_PX) setFollow(false);
  };

  return (
    <section className="rounded-[10px] border border-line bg-panel p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 className="text-[13px] font-semibold">Feed</h2>
        <Segmented
          label="Feed filter"
          value={kind}
          options={KINDS}
          onChange={(next) => setKind(next)}
        />
        <div className="ml-auto">
          <Switch checked={follow} onChange={setFollow} label="Follow" />
        </div>
      </div>
      {query.isError ? (
        <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />
      ) : query.isPending ? null : records.length === 0 ? (
        <p className="p-2 text-[13px] text-muted">{EMPTY[kind]}</p>
      ) : (
        <div
          ref={listRef}
          onScroll={onScroll}
          data-testid="feed-list"
          className="max-h-[420px] overflow-y-auto"
        >
          <ul>
            {records.map((record) => {
              const line = feedText(record);
              return (
                <li key={feedKey(active, record)} className="flex items-baseline gap-2 py-[3px]">
                  <span className="font-mono text-[11px] tabular-nums text-muted">
                    {hhmmss(record.ts)}
                  </span>
                  <span
                    aria-hidden="true"
                    className={`h-[6px] w-[6px] shrink-0 rounded-full ${TONE_DOT[line.tone]}`}
                  />
                  <span className="text-[13px]">{line.text}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
