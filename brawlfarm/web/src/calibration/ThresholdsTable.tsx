/**
 * The numbers the bot matches against, and what went wrong reading the file that can
 * change them.
 *
 * Every threshold is listed whether or not anyone has edited it, because they are the
 * numbers a reader comes here to check and a table that stayed empty until someone had
 * already edited the file would be no help at all. Everything else is here only when it
 * has been changed: an overridden constant, or a template image replaced in the
 * calibration folder.
 *
 * One column holds the value in use. A row whose packaged value differs says so in a
 * note under the value, rather than the table carrying a second column that repeated the
 * same figure on every row nobody has touched.
 *
 * Nothing in here is editable. The calibration folder is the only writer, and the source
 * column says which rows it wrote in the two words the legend explains.
 */
import { anchorLabel, constantLabel } from "./names";
import type { CalibrationConstant, CalibrationTemplate, ConstantValue } from "../api/calibration";
import { Chip } from "../components/ui/Chip";
import { Table, type Column } from "../components/ui/Table";

export interface ThresholdsTableProps {
  constants: readonly CalibrationConstant[];
  templates: readonly CalibrationTemplate[];
  file: { present: boolean; changed_since_start: boolean; problems: string[] };
}

export const CHANGED_WARNING =
  "The calibration file changed. Instances started before that keep the old values until you restart them.";

const LEGEND =
  "Package means the value brawlfarm ships. Override means you changed it in the calibration folder.";

/** Where a row's value came from. "file" is the calibration file and "templates" is the
 * folder of images beside it; both read as one word, override, because the distinction is
 * the reader's own folder either way. */
type Source = "package" | "file" | "templates";

interface Row {
  key: string;
  name: string;
  value: string;
  source: Source;
  /** The packaged value, worded, when it is not the value in use. */
  note: string | null;
}

/** A tap is a pair of pixels; everything else is one number, printed as it arrived so a
 * threshold of 0.85 does not become 0.9. */
function show(value: ConstantValue): string {
  return Array.isArray(value) ? `${value[0]}, ${value[1]}` : String(value);
}

/** Every threshold, then the constants someone has changed, then the templates someone
 * has replaced. No constant is listed twice, and the order inside each group is the
 * API's own. */
export function thresholdRows(
  constants: readonly CalibrationConstant[],
  templates: readonly CalibrationTemplate[],
): Row[] {
  const listed = [
    ...constants.filter((constant) => constant.group === "threshold"),
    ...constants.filter(
      (constant) => constant.group !== "threshold" && constant.source !== "package",
    ),
  ];
  const rows: Row[] = listed.map((constant) => {
    const value = show(constant.value);
    const packaged = show(constant.default);
    return {
      key: `constant:${constant.name}`,
      name: constant.name,
      value,
      source: constant.source === "package" ? "package" : "file",
      note: packaged === value ? null : `Packaged value ${packaged}`,
    };
  });
  for (const template of templates) {
    if (template.source !== "override") continue;
    rows.push({
      key: `template:${template.name}`,
      name: template.name,
      // The image itself is the override; the confidence it has to clear is the one
      // number the page is given about it, and the packaged image's own is not reported.
      value: show(template.threshold),
      source: "templates",
      note: null,
    });
  }
  return rows;
}

/** A template row is named after the anchor it is matched against, so the same image
 * reads the same way here as it does in the table of what the bot looks for. */
function settingLabel(row: Row): string {
  return row.source === "templates" ? anchorLabel(row.name) : constantLabel(row.name);
}

const COLUMNS: readonly Column<Row>[] = [
  { key: "name", label: "Setting", render: (row) => settingLabel(row) },
  {
    key: "value",
    label: "Value",
    width: "160px",
    render: (row) => (
      <span className="flex flex-col">
        <span className="t-figure">{row.value}</span>
        {row.note === null ? null : <span className="text-[11px] text-muted">{row.note}</span>}
      </span>
    ),
  },
  {
    key: "source",
    label: "Source",
    width: "120px",
    render: (row) =>
      row.source === "package" ? (
        <span className="text-[12px] text-muted">package</span>
      ) : (
        <Chip tone="idle">override</Chip>
      ),
  },
];

export function ThresholdsTable({ constants, templates, file }: ThresholdsTableProps) {
  const rows = thresholdRows(constants, templates);
  const untouched = rows.length > 0 && rows.every((row) => row.source === "package");

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Thresholds</h2>
      {untouched && <p className="text-[12px] text-muted">Packaged values, no overrides.</p>}

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
        empty="No thresholds reported."
        headers="sentence"
      />

      <p className="text-[12px] text-muted">{LEGEND}</p>
    </section>
  );
}
