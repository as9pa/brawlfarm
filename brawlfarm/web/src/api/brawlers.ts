/** The one place the brawler icon URL is built. BrawlerIcon is its only caller; nothing
 * else should be constructing a path out of a brawler's name. */
export function brawlerIconHref(name: string): string {
  return `/api/brawlers/${encodeURIComponent(name)}/icon.png`;
}
