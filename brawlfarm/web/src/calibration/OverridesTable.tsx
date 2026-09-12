/**
 * What calibration.toml and the templates folder have changed, and what went wrong
 * reading them.
 *
 * Only the overridden constants are listed, plus the three thresholds whether or not
 * they are overridden: they are the numbers a reader comes here to check, and a table
 * that hid them until someone had already edited the file would be no help at all.
 *
 * Nothing in here is editable. The file is the only writer, which is why the source
 * column names it.
 */
import type { CalibrationConstant, CalibrationTemplate, ConstantValue } from "../api/calibration";
import { Chip } from "../components/ui/Chip";
import { Table, type Column } from "../components/ui/Table";

export interface OverridesTableProps {
  constants: readonly CalibrationConstant[];
  templates: readonly CalibrationTemplate[];
  file: { present: boolean; changed_since_start: boolean; problems: string[] };
}

export const CHANGED_WARNING =
  "calibration.toml changed. Instances started before that run the old values until restarted.";

interface Row {
  key: string;
  name: string;
  fallback: string;
  current: string;
  source: string | null;
}

/** A tap is a pair of pixels; everything else is one number, printed as it arrived so a
 * threshold of 0.85 does not become 0.9. */
function show(value: ConstantValue): string {
  return Array.isArray(value) ? `${value[0]}, ${value[1]}` : String(value);
}

/** Overridden constants first, then the thresholds, in the API's own order and with no
 * constant listed twice. */
export function overrideRows(
  constants: readonly CalibrationConstant[],
  templates: readonly CalibrationTemplate[],
): Row[] {
  const listed = constants.filter(
    (constant) => constant.source !== "package" || constant.group === "threshold",
  );
  const rows: Row[] = listed.map((constant) => ({
    key: `constant:${constant.name}`,
    name: constant.name,
    fallback: show(constant.default),
    current: show(constant.value),
    source: constant.source === "package" ? null : constant.source,
  }));
  for (const template of templates) {
    if (template.source !== "override") continue;
    rows.push({
      key: `template:${template.name}`,
      name: `${template.name}.png`,
      // The packaged image is still there, but the page never sees its size, so there is
      // nothing honest to print in the default column.
      fallback: "-",
      current: `${template.width}x${template.height} at ${template.threshold.toFixed(2)}`,
      source: "calibration/templates",
    });
  }
  return rows;
}

const COLUMNS: readonly Column<Row>[] = [
  { key: "name", label: "Constant", mono: true, render: (row) => row.name },
  { key: "default", label: "Default", mono: true, width: "140px", render: (row) => row.fallback },
  { key: "value", label: "Override", mono: true, width: "160px", render: (row) => row.current },
  {
    key: "source",
    label: "Source",
    width: "170px",
    render: (row) =>
      row.source === null ? (
        <span className="text-[12px] text-muted">package</span>
      ) : (
        <Chip tone="idle">{row.source}</Chip>
      ),
  },
];

export function OverridesTable({ constants, templates, file }: OverridesTableProps) {
  const rows = overrideRows(constants, templates);

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Overrides</h2>

      {file.problems.map((problem) => (
        <p
          key={problem}
          data-tone="bad"
          className="rounded-[6px] border border-line bg-panel-2 px-2 py-1.5 text-[12px] text-bad"
        >
          {problem}
        </p>
      ))}

      {file.changed_since_start && (
        <p
          data-tone="warn"
          className="rounded-[6px] border border-line bg-panel-2 px-2 py-1.5 text-[12px] text-warn"
        >
          {CHANGED_WARNING}
        </p>
      )}

      <Table
        columns={COLUMNS}
        rows={rows}
        rowKey={(row) => row.key}
        empty="No overrides. Every constant is the packaged one."
      />
    </section>
  );
}
