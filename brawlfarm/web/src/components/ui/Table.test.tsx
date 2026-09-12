/** The settings tables: real table semantics, one render function per column, a header the
 * actions column does not show but a screen reader still hears, and one full-width cell
 * when there is nothing to list. */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { type Column, Table } from "./Table";

interface Row {
  name: string;
  port: number;
}

const ROWS: Row[] = [
  { name: "Pie64", port: 5555 },
  { name: "Pie64_3", port: 5585 },
];

const COLUMNS: readonly Column<Row>[] = [
  { key: "name", label: "Name", mono: true, render: (row) => row.name },
  { key: "port", label: "ADB port", mono: true, width: "120px", render: (row) => String(row.port) },
  {
    key: "actions",
    label: "",
    render: (row) => <button type="button">{`Remove ${row.name}`}</button>,
  },
];

describe("Table", () => {
  it("is a real table with one header per column", () => {
    render(<Table columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} empty="nothing" />);
    expect(screen.getAllByRole("columnheader").map((th) => th.textContent)).toEqual([
      "Name",
      "ADB port",
      "actions",
    ]);
    // A column with no visible label is still announced, by its key, rather than handing a
    // screen reader a blank header.
    expect(
      screen.getByRole("columnheader", { name: "actions" }).querySelector(".sr-only"),
    ).not.toBeNull();
    expect(screen.getAllByRole("row")).toHaveLength(3); // the header row plus two
  });

  it("renders every cell through its column and puts mono on the ones that ask", () => {
    render(<Table columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} empty="nothing" />);
    const row = screen.getByRole("row", { name: /Pie64_3/ });
    const cells = within(row).getAllByRole("cell");
    expect(cells.map((cell) => cell.textContent)).toEqual(["Pie64_3", "5585", "Remove Pie64_3"]);
    expect(cells[0].className).toContain("font-mono");
    expect(cells[2].className).not.toContain("font-mono");
    expect(within(row).getByRole("button", { name: "Remove Pie64_3" })).toBeInTheDocument();
  });

  it("shows the empty slot in one cell that spans the table", () => {
    render(
      <Table
        columns={COLUMNS}
        rows={[]}
        rowKey={(row) => row.name}
        empty="No instances yet. Add one or scan for BlueStacks."
      />,
    );
    const cell = screen.getByRole("cell");
    expect(cell).toHaveTextContent("No instances yet. Add one or scan for BlueStacks.");
    expect(cell).toHaveAttribute("colspan", "3");
  });
});
