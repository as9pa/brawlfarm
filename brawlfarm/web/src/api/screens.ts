/** The instance's screen. Not JSON, so it bypasses api<T>() and builds its own ApiError
 * from the same helper.
 *
 * screenshotUrl is only ever a link ("Full size"): the browser fetches it, we do not.
 * fetchPreview is the polled one, and its whole job is to cost nothing when the frame has
 * not moved -- it sends back the ETag it was given, so the API can answer 304 with no
 * body, and it reports "no change" either way (a 304, or a 200 carrying the same ETag). */
import { ApiError, NETWORK_DETAIL, errorFrom } from "./client";

export interface PreviewFrame {
  blob: Blob;
  etag: string | null;
  /** The frame's own moment when the API stamped one, the moment it arrived otherwise. */
  takenAt: number;
}

export function screenshotUrl(name: string): string {
  return `/api/instances/${name}/screenshot.png`;
}

export function previewUrl(name: string): string {
  return `/api/instances/${name}/preview.jpg`;
}

/** The instance's latest preview frame, or null when it is the one `knownEtag` names. */
export async function fetchPreview(
  name: string,
  knownEtag: string | null,
): Promise<PreviewFrame | null> {
  let response: Response;
  try {
    response = await fetch(previewUrl(name), {
      cache: "no-store",
      ...(knownEtag === null ? {} : { headers: { "if-none-match": knownEtag } }),
    });
  } catch {
    throw new ApiError(0, NETWORK_DETAIL);
  }
  if (response.status === 304) return null;
  if (!response.ok) throw await errorFrom(response);
  const etag = response.headers.get("etag");
  if (etag !== null && etag === knownEtag) return null;
  return { blob: await response.blob(), etag, takenAt: takenAt(response) };
}

function takenAt(response: Response): number {
  const stamped = response.headers.get("last-modified");
  const at = stamped === null ? Number.NaN : Date.parse(stamped);
  return Number.isNaN(at) ? Date.now() : at;
}
