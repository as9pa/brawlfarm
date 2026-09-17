/**
 * The component kit: every control the panel owns, in every variant and state, on one
 * page.
 *
 * It exists so a change to a shared control can be looked at rather than imagined, and so
 * the captures in a pull request body come from one place instead of six screens. It is
 * dev-only: App.tsx mounts the route behind import.meta.env.DEV, which Vite replaces with
 * false in a production build so Rollup drops both the route and this file.
 *
 * Nothing here calls the API and nothing here uses a query hook. The captures are taken
 * with no server running, and a page that needed one would show a row of error blocks
 * instead of the controls it is meant to show. Every value below is written in this file.
 */
import { type ReactNode, useState } from "react";

import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { Field } from "../components/ui/Field";
import { Segmented } from "../components/ui/Segmented";
import { StateChip } from "../components/ui/StateChip";
import { Switch } from "../components/ui/Switch";
import { Table } from "../components/ui/Table";
import type { InstanceState } from "../api/types";
import { clock, dateTime, num, signed } from "../lib/format";
import type { Tone } from "../lib/states";
import { toast } from "../lib/toast";

const BUTTON_VARIANTS = ["primary", "secondary", "quiet", "danger"] as const;

const CHIP_TONES: readonly Tone[] = ["ok", "warn", "bad", "idle"];

const STATES: readonly InstanceState[] = [
  "farming",
  "stopped",
  "scheduled_break",
  "reconnecting",
  "offline",
  "starting",
  "stopping",
];

const RANGES = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
] as const;

type Range = (typeof RANGES)[number]["value"];

interface KitRow {
  name: string;
  trophies: number;
  delta: number;
}

const ROWS: readonly KitRow[] = [
  { name: "Pie64", trophies: 41250, delta: 86 },
  { name: "Pie65", trophies: 38112, delta: -12 },
  { name: "Pie66", trophies: 29004, delta: 0 },
];

/** The stamp every time on the page is written from, so the two clock shapes can be read
 * against each other. It carries no timezone because the API's stamps carry none either. */
const SAMPLE_STAMP = "2026-09-17T05:25:00";

/** The one string both text roles are set in, so the difference between the roles is the
 * only thing that changes across the pair. */
const SAMPLE_TEXT = "Pie64 41,250";

interface SectionProps {
  title: string;
  children: ReactNode;
}

function Section({ title, children }: SectionProps) {
  return (
    <section className="flex flex-col gap-3 rounded-panel border border-line bg-panel p-4">
      <h2 className="text-[13px] font-medium text-text">{title}</h2>
      {children}
    </section>
  );
}

/** A label above a sample, so a reader can tell which variant they are looking at without
 * counting along the row. */
function Sample({ title, children }: SectionProps) {
  return (
    <div className="flex flex-col items-start gap-1.5">
      <span className="text-[11px] text-muted">{title}</span>
      {children}
    </div>
  );
}

export function Kit() {
  const [on, setOn] = useState(true);
  const [name, setName] = useState("Pie64");
  const [port, setPort] = useState("5555");
  const [token, setToken] = useState("");
  const [range, setRange] = useState<Range>("week");
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" }>({
    key: "trophies",
    dir: "desc",
  });

  const onSort = (key: string) => {
    setSort((current) =>
      current.key === key
        ? { key, dir: current.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "desc" },
    );
  };

  return (
    <div className="flex flex-col gap-4 bg-ground p-4 text-text">
      <header className="flex flex-col gap-1">
        <h1 className="text-[15px] font-medium">Component kit</h1>
        <p className="text-[12px] text-muted">
          Every shared control, in every variant and state. This page is not
          part of the built panel.
        </p>
      </header>

      <Section title="Buttons">
        <div className="flex flex-wrap items-end gap-4">
          {BUTTON_VARIANTS.map((variant) => (
            <Sample key={variant} title={variant}>
              <div className="flex items-center gap-2">
                <Button variant={variant} size="sm">
                  Small
                </Button>
                <Button variant={variant} size="md">
                  Medium
                </Button>
              </div>
            </Sample>
          ))}
          <Sample title="disabled">
            <Button disabled disabledReason="Pie64 is already stopped">
              Stop
            </Button>
          </Sample>
        </div>
      </Section>

      <Section title="Switches">
        <div className="flex flex-wrap items-end gap-6">
          <Sample title="on">
            <Switch checked={on} onChange={setOn} label="Run overnight" />
          </Sample>
          <Sample title="off">
            <Switch
              checked={!on}
              onChange={(next) => setOn(!next)}
              label="Pause on a loss"
            />
          </Sample>
          <Sample title="on, disabled">
            <Switch
              checked
              onChange={() => {}}
              label="Run overnight"
              disabled
            />
          </Sample>
          <Sample title="off, disabled">
            <Switch
              checked={false}
              onChange={() => {}}
              label="Pause on a loss"
              disabled
            />
          </Sample>
        </div>
      </Section>

      <Section title="Fields">
        <div className="flex flex-wrap items-start gap-6">
          <Sample title="plain">
            <Field label="Name" id="kit-name" value={name} onChange={setName} />
          </Sample>
          <Sample title="with help">
            <Field
              label="Port"
              id="kit-port"
              value={port}
              onChange={setPort}
              help="The console port this instance answers on."
            />
          </Sample>
          <Sample title="with error">
            <Field
              label="Token"
              id="kit-token"
              value={token}
              onChange={setToken}
              type="password"
              error="Paste the token from the settings page."
            />
          </Sample>
          <Sample title="numeric">
            <Field
              label="Games"
              id="kit-games"
              value="12"
              onChange={() => {}}
              type="number"
              inputMode="numeric"
              min={0}
              step={1}
              suffix="games"
            />
          </Sample>
        </div>
      </Section>

      <Section title="Segmented">
        <Segmented
          value={range}
          options={RANGES}
          onChange={setRange}
          label="Range"
        />
      </Section>

      <Section title="Table">
        <p className="text-[11px] text-muted">
          Trophies is sortable: tab to its header for the ring every other
          control uses.
        </p>
        <Table
          columns={[
            { key: "name", label: "Instance", width: "160px" },
            {
              key: "trophies",
              label: "Trophies",
              mono: true,
              sortable: true,
              render: (row: KitRow) => num(row.trophies),
            },
            {
              key: "delta",
              label: "Today",
              mono: true,
              render: (row: KitRow) => signed(row.delta),
            },
          ]}
          rows={ROWS}
          rowKey={(row) => row.name}
          empty="No instances yet."
          sort={sort}
          onSort={onSort}
        />
      </Section>

      <Section title="Chips">
        <div className="flex flex-wrap items-end gap-6">
          <Sample title="Chip">
            <div className="flex flex-wrap items-center gap-2">
              {CHIP_TONES.map((tone) => (
                <Chip key={tone} tone={tone}>
                  {tone}
                </Chip>
              ))}
            </div>
          </Sample>
          <Sample title="StateChip">
            <div className="flex flex-wrap items-center gap-2">
              {STATES.map((state) => (
                <StateChip key={state} state={state} />
              ))}
            </div>
          </Sample>
        </div>
      </Section>

      <Section title="Toasts">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => toast("Plan saved", { tone: "ok" })}>
            Show an ok toast
          </Button>
          <Button
            onClick={() =>
              toast("That did not go through. Try again.", {
                tone: "bad",
                retry: () => {},
              })
            }
          >
            Show a bad toast
          </Button>
          <Button onClick={() => toast("Pie64 is on a break until 07:00")}>
            Show an info toast
          </Button>
        </div>
      </Section>

      <Section title="Text roles">
        <div className="flex flex-wrap items-end gap-6">
          <Sample title="t-figure">
            <span className="t-figure text-[13px]">{SAMPLE_TEXT}</span>
          </Sample>
          <Sample title="t-name">
            <span className="t-name text-[13px]">{SAMPLE_TEXT}</span>
          </Sample>
          <Sample title="num, signed, clock and dateTime">
            <span className="t-figure text-[13px]">
              {num(41250)} {signed(86)} {clock(SAMPLE_STAMP)}{" "}
              {dateTime(SAMPLE_STAMP)}
            </span>
          </Sample>
        </div>
      </Section>

      <Section title="Radius">
        <div className="flex flex-wrap items-end gap-6">
          <Sample title="rounded-control, 6 px">
            <div className="h-8 w-24 rounded-control border border-line bg-panel-2" />
          </Sample>
          <Sample title="rounded-panel, 10 px">
            <div className="h-8 w-24 rounded-panel border border-line bg-panel-2" />
          </Sample>
          <Sample title="rounded-chip, pill">
            <div className="h-8 w-24 rounded-chip border border-line bg-panel-2" />
          </Sample>
        </div>
      </Section>
    </div>
  );
}
