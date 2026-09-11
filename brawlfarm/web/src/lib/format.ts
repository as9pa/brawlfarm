/** Number and word formatting: signed deltas, and nouns that agree with their count. */

export function signed(n: number): string {
  if (n === 0) return "0";
  return n > 0 ? `+${n}` : String(n);
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}
