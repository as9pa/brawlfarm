/**
 * The panel's one table.
 *
 * A real <table> with a <th scope="col"> per column, because both settings tables are
 * genuinely tabular and a grid of divs hands a screen reader a wall of unrelated text. A
 * column has no value accessor: `render` is how every cell gets its content, which is what
 * lets a status chip, an inline field and a row of buttons all be ordinary columns.
 *
 * The table sits in its own overflow-x-auto box, because at phone width the columns add up
 * to more than the panel is wide and a table that pushes the page sideways takes the whole
 * layout with it. Both callers want that, so it lives here rather than in either of them.
 *
 * A column whose label is empty still gets a header cell, named by its key and hidden with
 * sr-only on a span inside the cell rather than on the cell itself: sr-only is
 * position:absolute, and that would take the header out of the table's column flow.
 *
 * The overflow box is itself positioned so that absolutely positioned span stays clipped
 * inside it instead of escaping to the nearest positioned ancestor.
 *
 * A table with a `minWidth` overflows on a narrow panel, so it also gets a fading strip down
 * its right edge: a table that has to be scrolled sideways needs to look like one. The strip
 * is decoration and nothing else, so it is aria-hidden and takes no pointer events. It is a
 * sibling of the overflow box rather than a child of it, positioned on a wrapper of its own:
 * inside the box it would be placed against the scrolling content and slide off the edge it
 * is there to mark. A table with no `minWidth` grows no wrapper and renders exactly as it
 * always has.
 *
 * `nowrap` is for a table that scrolls: a cell that wraps has not been saved from squeezing,
 * it has been squeezed vertically instead, and one two-line placeholder makes its row twice
 * the height of every other row.
 *
 * Sorting is opt-in and is the caller's job. With `sort` and `onSort` a sortable column's
 * label becomes a full-width button and its <th> carries aria-sort; without them no header
 * is a button and no aria-sort is written, so every call site that predates this renders
 * exactly as it did. The table never reorders `rows`: the caller owns the order, because
 * only the caller knows how to compare its own values.
 */
import { ChevronDown, ChevronUp } from "lucide-react";
import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  label: string;
  /** The long answer a short header cannot hold, as the header cell's tooltip. */
  title?: string;
  mono?: boolean;
  /** A CSS track for this column, e.g. "120px", written onto its <col>. */
  width?: string;
  render?: (row: Row) => ReactNode;
  sortable?: boolean;
}

export interface TableProps<Row> {
  columns: readonly Column<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  empty: ReactNode;
  sort?: { key: string; dir: "asc" | "desc" };
  onSort?: (key: string) => void;
  /** A CSS length written onto the table, so a table with more columns than the panel is
   * wide scrolls inside its own box instead of squeezing every column. */
  minWidth?: string;
  /** How the headers read. Caps is the house style for a settings table of fields; a
   * table of figures a person scans down reads in sentence case. */
  headers?: "caps" | "sentence";
  /** Keeps every cell on one line, so a long value widens the table and the box scrolls
   * rather than the row growing a second line. Pairs with `minWidth`. */
  nowrap?: boolean;
}

/** The one focus ring, restated on the control so it survives an ancestor that sets
 * outline-none. theme.css carries the same rule as the fallback. */
const FOCUS_RING =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

/** The two header styles. Written out rather than composed, so the caps one is the same
 * string it has always been and the six tables that predate this render byte for byte. */
const HEADER: Record<"caps" | "sentence", string> = {
  caps: "px-2 py-1.5 text-left text-[11px] font-medium uppercase tracking-wide text-muted",
  sentence: "px-2 py-1.5 text-left text-[11px] font-medium text-muted",
};

/** The casing half of the same two styles. A sortable column's label lives in a button
 * inside the th, and both halves of one header have to read the same way. */
const HEADER_CASE: Record<"caps" | "sentence", string> = {
  caps: "uppercase tracking-wide",
  sentence: "",
};

export function Table<Row>({
  columns,
  rows,
  rowKey,
  empty,
  sort,
  onSort,
  minWidth,
  headers = "caps",
  nowrap = false,
}: TableProps<Row>) {
  const sorting = sort !== undefined && onSort !== undefined;

  const ariaSort = (column: Column<Row>): "ascending" | "descending" | "none" | undefined => {
    if (!sorting || column.sortable !== true) return undefined;
    if (sort.key !== column.key) return "none";
    return sort.dir === "asc" ? "ascending" : "descending";
  };

  const box = (
    <div className="relative overflow-x-auto">
      <table
        className="w-full border-collapse text-[13px]"
        style={minWidth === undefined ? undefined : { minWidth }}
      >
        <colgroup>
          {columns.map((column) => (
            <col
              key={column.key}
              style={column.width === undefined ? undefined : { width: column.width }}
            />
          ))}
        </colgroup>
        <thead>
          <tr className="border-b border-line">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                title={column.title}
                aria-sort={ariaSort(column)}
                className={HEADER[headers]}
              >
                {sorting && column.sortable === true ? (
                  <button
                    type="button"
                    onClick={() => onSort(column.key)}
                    className={`flex w-full items-center gap-1 text-left ${FOCUS_RING} ${HEADER_CASE[headers]}`}
                  >
                    {column.label === "" ? (
                      <span className="sr-only">{column.key}</span>
                    ) : (
                      column.label
                    )}
                    {sort.key === column.key ? (
                      sort.dir === "asc" ? (
                        <ChevronUp aria-hidden="true" size={12} strokeWidth={1.6} />
                      ) : (
                        <ChevronDown aria-hidden="true" size={12} strokeWidth={1.6} />
                      )
                    ) : null}
                  </button>
                ) : column.label === "" ? (
                  <span className="sr-only">{column.key}</span>
                ) : (
                  column.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-2 py-3 text-[13px] text-muted">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={rowKey(row)} className="border-b border-line last:border-b-0 hover:bg-panel-2">
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-2 py-1.5 align-middle ${column.mono === true ? "font-mono tabular-nums" : ""} ${nowrap ? "whitespace-nowrap" : ""}`}
                  >
                    {column.render === undefined ? null : column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );

  if (minWidth === undefined) return box;

  return (
    <div className="relative">
      {box}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-panel to-transparent"
      />
    </div>
  );
}
