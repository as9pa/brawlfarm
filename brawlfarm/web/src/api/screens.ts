/** The live screenshot. Not JSON, so it bypasses api<T>() and builds its own ApiError
 * from the same helper; the API sends Cache-Control: no-store and we ask for no-store
 * again, because a cached frame is a stale screen. */
import { ApiError, NETWORK_DETAIL, errorFrom } from "./client";

export function screenshotUrl(name: string): string {
  return `/api/instances/${name}/screenshot.png`;
}

export async function fetchScreenshot(name: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(screenshotUrl(name), { cache: "no-store" });
  } catch {
    throw new ApiError(0, NETWORK_DETAIL);
  }
  if (!response.ok) throw await errorFrom(response);
  return response.blob();
}
