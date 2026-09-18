/** The settings tables: real table semantics, one render function per column, a header the
 * actions column does not show but a screen reader still hears, and one full-width cell
 * when there is nothing to list. */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { type Column, Table } from "./Table";
import { renderWithProviders } from "../../test/renderWithProviders";

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
  it("reads its headers in caps by default and in sentence case when asked", () => {
    const { unmount } = render(
      <Table
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.name}
        empty="nothing"
        headers="sentence"
      />,
    );
    expect(screen.getByRole("columnheader", { name: "Name" }).className).not.toContain(
      "uppercase",
    );
    unmount();
    render(<Table columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} empty="nothing" />);
    expect(screen.getByRole("columnheader", { name: "Name" }).className).toContain("uppercase");
  });

  it("puts a minimum width on the table element itself", () => {
    const { container } = render(
      <Table
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.name}
        empty="nothing"
        minWidth="720px"
      />,
    );
    expect(container.querySelector("table")).toHaveStyle({ minWidth: "720px" });
  });

  it("cues the scrollable edge only when there is a minimum width", () => {
    const { container, unmount } = render(
      <Table
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.name}
        empty="nothing"
        minWidth="720px"
      />,
    );
    const cue = container.querySelector('span[aria-hidden="true"].pointer-events-none');
    expect(cue).not.toBeNull();
    // Outside the scrolling box, or it would slide off the edge it is there to mark.
    expect(cue?.parentElement?.className).toBe("relative");
    expect(cue?.previousElementSibling?.className).toContain("overflow-x-auto");
    unmount();
    const plain = render(
      <Table columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} empty="nothing" />,
    );
    expect(
      plain.container.querySelector('span[aria-hidden="true"].pointer-events-none'),
    ).toBeNull();
  });

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

  it("writes no aria-sort and no header button without the new props", () => {
    renderWithProviders(
      <Table
        columns={[
          { key: "name", label: "Brawler", sortable: true },
          { key: "games", label: "Games", sortable: true },
        ]}
        rows={[{ name: "NORI", games: 3 }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
      />,
    );
    for (const header of screen.getAllByRole("columnheader")) {
      expect(header).not.toHaveAttribute("aria-sort");
      expect(within(header).queryByRole("button")).toBeNull();
    }
  });

  it("writes aria-sort on the sorted column and none on the others", () => {
    renderWithProviders(
      <Table
        columns={[
          { key: "name", label: "Brawler", sortable: true },
          { key: "games", label: "Games", sortable: true },
          { key: "icon", label: "", width: "34px" },
        ]}
        rows={[{ name: "NORI", games: 3 }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
        sort={{ key: "games", dir: "desc" }}
        onSort={() => undefined}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "Games" })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    expect(screen.getByRole("columnheader", { name: "Brawler" })).toHaveAttribute(
      "aria-sort",
      "none",
    );
    // A column that is not sortable gets no aria-sort at all, sorted table or not.
    expect(screen.getByRole("columnheader", { name: "icon" })).not.toHaveAttribute("aria-sort");
  });

  it("gives a sortable header's button the casing the headers prop asked for", () => {
    renderWithProviders(
      <Table
        columns={[
          { key: "name", label: "Brawler", sortable: true },
          { key: "games", label: "Games", sortable: true },
        ]}
        rows={[{ name: "NORI", games: 3 }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
        headers="sentence"
        sort={{ key: "games", dir: "desc" }}
        onSort={() => undefined}
      />,
    );
    expect(screen.getByRole("button", { name: "Brawler" }).className).not.toContain("uppercase");
  });

  it("calls onSort once per header click, with that column's key", async () => {
    const onSort = vi.fn();
    renderWithProviders(
      <Table
        columns={[
          { key: "name", label: "Brawler", sortable: true },
          { key: "games", label: "Games", sortable: true },
        ]}
        rows={[{ name: "NORI", games: 3 }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
        sort={{ key: "games", dir: "desc" }}
        onSort={onSort}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Brawler" }));
    expect(onSort).toHaveBeenCalledTimes(1);
    expect(onSort).toHaveBeenCalledWith("name");
  });

  it("never reorders the rows it was given", () => {
    renderWithProviders(
      <Table
        columns={[{ key: "name", label: "Brawler", sortable: true, render: (r) => r.name }]}
        rows={[
          { name: "SHELLY", games: 1 },
          { name: "NORI", games: 3 },
        ]}
        rowKey={(row) => row.name}
        empty="No games in this range."
        sort={{ key: "name", dir: "asc" }}
        onSort={() => undefined}
      />,
    );
    const cells = screen.getAllByRole("cell").map((cell) => cell.textContent);
    expect(cells).toEqual(["SHELLY", "NORI"]);
  });

  it("carries the shared focus ring on the sort control", () => {
    renderWithProviders(
      <Table
        columns={[{ key: "name", label: "Brawler", sortable: true, render: (r) => r.name }]}
        rows={[{ name: "SHELLY" }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
        sort={{ key: "name", dir: "asc" }}
        onSort={() => undefined}
      />,
    );
    const header = screen.getByRole("columnheader", { name: "Brawler" });
    expect(within(header).getByRole("button").className).toContain(
      "focus-visible:outline-accent",
    );
  });
});
