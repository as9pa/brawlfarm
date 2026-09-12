/** One setting: its name, the plain sentence under it, the control beside it, and the
 * API's own message when that control's last save was refused. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingRow } from "./SettingRow";
import { Switch } from "../components/ui/Switch";

describe("SettingRow", () => {
  it("shows the title, the sentence and the control", () => {
    render(
      <SettingRow title="Gas aware" description="Move away from the gas earlier.">
        <Switch checked onChange={vi.fn()} label="Gas aware" />
      </SettingRow>,
    );
    expect(screen.getByText("Move away from the gas earlier.")).toBeInTheDocument();
    // The words appear twice in the DOM and once on screen: the row prints the title, and
    // the switch keeps the same string as its accessible name with its own copy shrunk
    // away. Switch's props are phase 4's and do not change, so the row is what hides it.
    expect(screen.getAllByText("Gas aware").map((el) => el.tagName)).toEqual(["P", "BUTTON"]);
    expect(screen.getByRole("switch", { name: "Gas aware" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("prints the field error under both", () => {
    render(
      <SettingRow
        title="ADB path"
        description="Where HD-Adb.exe lives."
        error="adb_path: file not found"
      >
        <Switch checked={false} onChange={vi.fn()} label="ADB path" />
      </SettingRow>,
    );
    expect(screen.getByText("adb_path: file not found")).toBeInTheDocument();
  });

  it("shows no error line when there is no error", () => {
    const { container } = render(
      <SettingRow title="Bush hide" description="Hide in bushes when the map allows.">
        <Switch checked={false} onChange={vi.fn()} label="Bush hide" />
      </SettingRow>,
    );
    expect(container.querySelector(".text-bad")).toBeNull();
  });
});
