/** The guard that keeps the panel's internal vocabulary off the screen. It reads the
 * source tree instead of rendering anything, because a word can reach a reader from any
 * of a hundred files and no suite renders them all.
 *
 * Comments and identifiers are free to say worker, supervisor and tick: that is what the
 * code calls these things. Only what a person reads is checked, which here means a string
 * literal or a line of JSX text. */
import { describe, expect, it } from "vitest";

/** Empty on purpose. A string that truly needs one of these words adds its own
 * `path:line: text` entry here, in the same commit, with a comment saying why. */
const ALLOWED: readonly string[] = [];

/** The whole tree under src, read as text at transform time. Vite does the walking
 * because the panel has no node types installed, and a raw import needs none. */
const TREE: Record<string, string> = Object.fromEntries(
  Object.entries(
    import.meta.glob("/src/**/*.{ts,tsx}", {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>,
  ).map(([key, text]) => [key.replace("/src/", ""), text]),
);

/** Every file a reader's words can come from, named relative to src. The suites and the
 * test helpers are left out, because their strings are fixtures rather than copy. */
function sources(): string[] {
  return Object.keys(TREE)
    .filter((rel) => !/\.test\.tsx?$/.test(rel) && !rel.startsWith("test/"))
    .sort();
}

type Kind = "code" | "literal" | "interp";

/** One run of source text on one line, with comments already dropped. `interp` marks a
 * template chunk that an ${...} follows, which is the only place a key=value shape can
 * hide. */
interface Piece {
  line: number;
  kind: Kind;
  text: string;
}

/**
 * Splits a file into code and string-literal pieces, dropping line comments, block
 * comments and JSDoc on the way. One character at a time rather than a regex, because a
 * quote inside a comment and a `//` inside a URL both break the regex versions.
 */
function pieces(source: string): Piece[] {
  const out: Piece[] = [];
  let state: Kind | "line" | "block" = "code";
  let quote = "";
  // A template literal's ${...} holds code, which can open a template of its own; the
  // stack remembers how many templates the closing braces have to walk back into.
  const templates: string[] = [];
  let line = 1;
  let start = 1;
  let buf = "";
  const flush = (kind: Kind) => {
    if (buf.trim() !== "") out.push({ line: start, kind, text: buf });
    buf = "";
    start = line;
  };
  for (let i = 0; i < source.length; i += 1) {
    const c = source[i];
    const next = source[i + 1] ?? "";
    if (c === "\n") {
      // Pieces never span a line, so every hit can name the line it is on.
      if (state === "code" || state === "literal") flush(state);
      if (state === "line") {
        buf = "";
        state = "code";
      }
      // A quoted string cannot hold a raw newline, so the line end closes it. That keeps
      // an apostrophe in JSX text or a quote inside a regex from swallowing the rest of
      // the file: the mistake costs one line, not the whole scan.
      if (state === "literal" && quote !== "`") state = "code";
      line += 1;
      start = line;
      continue;
    }
    if (state === "line") continue;
    if (state === "block") {
      if (c === "*" && next === "/") {
        buf = "";
        state = "code";
        start = line;
        i += 1;
      }
      continue;
    }
    if (state === "literal") {
      if (c === "\\") {
        i += 1;
        continue;
      }
      if (quote === "`" && c === "$" && next === "{") {
        flush("interp");
        templates.push(quote);
        state = "code";
        i += 1;
        continue;
      }
      if (c === quote) {
        flush("literal");
        state = "code";
        continue;
      }
      buf += c;
      continue;
    }
    if (c === "/" && next === "/") {
      flush("code");
      state = "line";
      continue;
    }
    if (c === "/" && next === "*") {
      flush("code");
      state = "block";
      i += 1;
      continue;
    }
    if (c === "'" || c === '"' || c === "`") {
      flush("code");
      quote = c;
      state = "literal";
      continue;
    }
    if (c === "}" && templates.length > 0) {
      flush("code");
      quote = templates.pop() ?? "`";
      state = "literal";
      continue;
    }
    buf += c;
  }
  if (state === "code" || state === "literal") flush(state);
  return out;
}

const INTERNAL = /\b(workers?|supervisors?|ticks?)\b/i;
const PYTHON_TRUE = /\bTrue\b/;
const RAW_FLOAT = /=0\./;
const KEY_VALUE = /[A-Za-z_]\w*=\s*$/;
/** A query string is key=value by design and no reader sees it, so a chunk carrying a
 * URL's own punctuation is not a leaked field. */
const QUERY = /^[/]|[?&]/;
const TAG = /<[^<>]*>/g;
/** One name or member chain alone on a line, which is the shape an interpolation or a
 * wrapped argument leaves behind. Prose has spaces in it. */
const BARE_NAME = /^[\w$.]+,?$/;
/** A line of JSX text is prose and nothing else: an operator or a brace means the piece
 * is code, and code may call things whatever it likes. */
const CODE_CHARS = /[{}()[\]=;:&|<>]/;

/** The words a reader would see in this piece, which is the piece itself for a string
 * literal and the text between the tags for a line of JSX. */
function readable(piece: Piece): string {
  if (piece.kind !== "code") return piece.text;
  const bare = piece.text.replace(TAG, " ");
  if (CODE_CHARS.test(bare) || !/[A-Za-z]/.test(bare)) return "";
  if (BARE_NAME.test(bare.trim())) return "";
  return bare;
}

function scan(rel: string): string[] {
  const hits: string[] = [];
  const report = (piece: Piece) =>
    hits.push(`${rel}:${piece.line}: ${piece.text.trim()}`);
  for (const piece of pieces(TREE[rel])) {
    if (INTERNAL.test(readable(piece))) report(piece);
    else if (PYTHON_TRUE.test(piece.text)) report(piece);
    else if (RAW_FLOAT.test(piece.text)) report(piece);
    else if (piece.kind === "interp" && KEY_VALUE.test(piece.text) && !QUERY.test(piece.text))
      report(piece);
  }
  return hits;
}

describe("the words a reader never sees", () => {
  it("reads the whole source tree", () => {
    const files = sources();
    expect(files).toContain("lib/copy.ts");
    expect(files).toContain("instance/Feed.tsx");
    expect(files.some((rel) => rel.startsWith("test/"))).toBe(false);
    expect(files.some((rel) => rel.includes(".test."))).toBe(false);
    expect(files.length).toBeGreaterThan(40);
  });

  it("keeps worker, supervisor, tick, True and key=value off the screen", () => {
    const hits = sources()
      .flatMap(scan)
      .filter((hit) => !ALLOWED.includes(hit));
    // One message with every hit, so a failure names all of them at once.
    expect(hits.join("\n")).toBe("");
  });
});
