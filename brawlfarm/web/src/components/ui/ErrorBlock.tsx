/**
 * A failure the user can read.
 *
 * The API's `detail` is printed verbatim, because it was written for a person: "adb did
 * not answer", "Stop Pie64 before removing it". A 422 adds one line per field. Anything
 * that is not an ApiError still gets a sentence rather than a stack trace.
 */
import { Button } from "./Button";
import { ApiError } from "../../api/client";

export interface ErrorBlockProps {
  error: unknown;
  onRetry?: () => void;
}

function describe(error: unknown): { detail: string; lines: string[] } {
  if (error instanceof ApiError) return { detail: error.detail, lines: error.lines };
  if (error instanceof Error) return { detail: error.message, lines: [] };
  return { detail: "Request failed", lines: [] };
}

export function ErrorBlock({ error, onRetry }: ErrorBlockProps) {
  const { detail, lines } = describe(error);
  return (
    <div className="rounded-[10px] border border-line bg-panel p-3">
      <p className="text-[13px] text-bad">{detail}</p>
      {lines.length > 0 && (
        <ul className="mt-1 space-y-0.5">
          {lines.map((line) => (
            <li key={line} className="font-mono text-[11px] text-muted">
              {line}
            </li>
          ))}
        </ul>
      )}
      {onRetry !== undefined && (
        <div className="mt-2">
          <Button variant="quiet" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}
