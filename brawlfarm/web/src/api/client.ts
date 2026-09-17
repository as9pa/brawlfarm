/**
 * The panel's one HTTP door.
 *
 * Every call goes through api<T>() so a failure always arrives as an ApiError carrying a
 * sentence ErrorBlock can print: the API's own `detail` string when it sent one, the
 * lines of FastAPI's validation list when it sent that instead, the status otherwise,
 * and the panel's own wording when fetch itself could not reach the server.
 */

export const NETWORK_DETAIL = "The panel cannot reach brawlfarm. Is it still running?";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly lines: string[] = [],
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

interface ValidationItem {
  loc: (string | number)[];
  msg: string;
}

function isValidationItem(value: unknown): value is ValidationItem {
  if (typeof value !== "object" || value === null) return false;
  const item = value as { loc?: unknown; msg?: unknown };
  return Array.isArray(item.loc) && typeof item.msg === "string";
}

/** FastAPI's 422 body is a list of {loc, msg}; anything else has no lines. */
export function validationLines(detail: unknown): string[] {
  if (!Array.isArray(detail)) return [];
  return detail.filter(isValidationItem).map((item) => `${item.loc.join(".")}: ${item.msg}`);
}

/** The 422 sentence, which both the status map and a validation-lines error use. */
const VALIDATION_MESSAGE = "Some values were not accepted. Fix the fields listed and try again.";

/** One sentence per status the API answers with, each ending in the step the reader can
 * take next. A status this map does not name reads through the generic sentence below. */
const STATUS_MESSAGE: Record<number, string> = {
  400: "That request was not valid. Check the values and try again.",
  401: "The panel is not signed in to brawlfarm. Check the API token in Settings.",
  403: "The panel is not allowed to do that. Check the API token in Settings.",
  404: "That is not there any more. Refresh the page.",
  409: "Something changed while you were editing. Refresh and try again.",
  422: VALIDATION_MESSAGE,
  500: "brawlfarm hit an internal error. Check the panel log, then try again.",
  503: "brawlfarm is not ready yet. Wait a moment and try again.",
};

export async function errorFrom(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  const detail = (body as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return new ApiError(response.status, detail);
  const lines = validationLines(detail);
  if (lines.length > 0) return new ApiError(response.status, VALIDATION_MESSAGE, lines);
  const generic = `Something went wrong (HTTP ${response.status}). Try again, and check the panel log if it keeps failing.`;
  return new ApiError(response.status, STATUS_MESSAGE[response.status] ?? generic);
}

function withJsonHeaders(init: RequestInit | undefined): RequestInit {
  if (init?.body === undefined) return { ...init };
  return { ...init, headers: { "content-type": "application/json", ...init.headers } };
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, withJsonHeaders(init));
  } catch {
    // fetch only rejects when the request never got an answer: the server is down, or
    // the browser refused to send it. Either way the panel says the same thing.
    throw new ApiError(0, NETWORK_DETAIL);
  }
  if (!response.ok) throw await errorFrom(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
