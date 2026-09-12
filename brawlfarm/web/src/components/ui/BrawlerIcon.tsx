/**
 * A brawler's portrait, or its initial.
 *
 * Decorative on purpose: the name is always beside it, so the square is aria-hidden and
 * the image's alt is empty rather than a second reading of the same word.
 *
 * The square is laid out at its final size before the image resolves and keeps that size
 * in every state, so a table of twenty rows does not shuffle as the icons arrive. There is
 * no retry, no timer and no cache here: the browser's HTTP cache plus the route's
 * week-long Cache-Control is the cache.
 */
import { useEffect, useState } from "react";

import { brawlerIconHref } from "../../api/brawlers";

export interface BrawlerIconProps {
  name: string | null;
  size?: number;
}

const DEFAULT_SIZE = 22;

export function BrawlerIcon({ name, size = DEFAULT_SIZE }: BrawlerIconProps) {
  const trimmed = (name ?? "").trim();
  const [failed, setFailed] = useState(false);

  // A row that scrolls into a different brawler must try again: the failure belonged to
  // the previous name, not to this square.
  useEffect(() => {
    setFailed(false);
  }, [trimmed]);

  const square = { width: `${size}px`, height: `${size}px` };

  return (
    <span
      data-testid="brawler-icon"
      aria-hidden="true"
      className="inline-flex items-center justify-center"
      style={{
        ...square,
        borderRadius: "6px",
        overflow: "hidden",
        background: "var(--panel-2)",
        flex: "none",
      }}
    >
      {trimmed === "" || failed ? (
        <span className="text-[11px] leading-none text-muted">
          {trimmed.slice(0, 1).toUpperCase()}
        </span>
      ) : (
        <img
          src={brawlerIconHref(trimmed)}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          style={square}
        />
      )}
    </span>
  );
}
