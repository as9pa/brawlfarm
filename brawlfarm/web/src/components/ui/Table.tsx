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
 */
import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  label: string;
  mono?: boolean;
  /** A CSS track for this column, e.g. "120px", written onto its <col>. */
  width?: string;
  render?: (row: Row) => ReactNode;
}

export interface TableProps<Row> {
  columns: readonly Column<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  empty: ReactNode;
}

export function Table<Row>({ columns, rows, rowKey, empty }: TableProps<Row>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
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
                className="px-2 py-1.5 text-left text-[11px] font-medium uppercase tracking-wide text-muted"
              >
                {column.label === "" ? <span className="sr-only">{column.key}</span> : column.label}
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
                    className={`px-2 py-1.5 align-middle ${column.mono === true ? "font-mono tabular-nums" : ""}`}
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
}
