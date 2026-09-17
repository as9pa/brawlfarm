/** A labelled input with a suffix, so "Goal 1000 trophies" is one control, not three. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Field } from "./Field";

describe("Field", () => {
  it("ties the label to the input and reports what was typed", async () => {
    const onChange = vi.fn();
    render(
      <Field
        label="Goal"
        id="goal"
        value="1000"
        onChange={onChange}
        type="number"
        suffix="trophies"
        min={0}
      />,
    );
    const input = screen.getByLabelText("Goal");
    expect(input).toHaveValue(1000);
    expect(input).toHaveAttribute("min", "0");
    expect(screen.getByText("trophies")).toBeInTheDocument();
    await userEvent.type(input, "1");
    expect(onChange).toHaveBeenLastCalledWith("10001");
  });

  it("passes a datalist id through so the roster can suggest brawlers", () => {
    render(
      <Field label="Fallback brawler" id="fallback" value="" onChange={vi.fn()} list="roster" disabled />,
    );
    const input = screen.getByLabelText("Fallback brawler");
    expect(input).toHaveAttribute("list", "roster");
    expect(input).toBeDisabled();
  });

  it("masks the token, keeps browsers out of it, and toggles with Show and Hide", async () => {
    render(
      <Field
        label="Brawl Stars API token"
        id="token"
        value="a-token-that-is-not-real"
        onChange={vi.fn()}
        type="password"
        width="full"
      />,
    );
    const input = screen.getByLabelText("Brawl Stars API token");
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveAttribute("autocomplete", "off");
    // The screenshot pass blurs every [data-private] before the shot is taken.
    expect(input).toHaveAttribute("data-private");

    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(input).toHaveAttribute("type", "text");
    expect(screen.queryByRole("button", { name: "Show" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(input).toHaveAttribute("type", "password");
  });

  it("leaves an ordinary field alone: no mask, no reveal button, the control width", () => {
    render(<Field label="Goal" id="goal" value="1000" onChange={vi.fn()} type="number" />);
    const input = screen.getByLabelText("Goal");
    expect(input).toHaveAttribute("type", "number");
    expect(input).not.toHaveAttribute("data-private");
    expect(input).not.toHaveAttribute("autocomplete");
    expect(input.className).toContain("w-24");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("grows to the row when asked", () => {
    render(<Field label="ADB path" id="adb" value="C:/adb.exe" onChange={vi.fn()} width="full" />);
    const input = screen.getByLabelText("ADB path");
    expect(input.className).toContain("w-full");
    expect(input.className).not.toContain("w-24");
  });

  it("renders a help line under the control and points the input at it", () => {
    render(
      <Field label="ADB path" id="adb" value="" onChange={vi.fn()} help="Where adb.exe lives." />,
    );
    const input = screen.getByLabelText("ADB path");
    expect(screen.getByText("Where adb.exe lives.")).toHaveAttribute("id", "adb-msg");
    expect(input).toHaveAttribute("aria-describedby", "adb-msg");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input.className).toContain("border-line");
  });

  it("lets an error replace the help line, announce itself and colour the border", () => {
    render(
      <Field
        label="ADB path"
        id="adb"
        value=""
        onChange={vi.fn()}
        help="Where adb.exe lives."
        error="That path does not exist."
      />,
    );
    const input = screen.getByLabelText("ADB path");
    expect(screen.queryByText("Where adb.exe lives.")).not.toBeInTheDocument();
    const message = screen.getByRole("alert");
    expect(message).toHaveTextContent("That path does not exist.");
    expect(message).toHaveAttribute("id", "adb-msg");
    expect(input).toHaveAttribute("aria-describedby", "adb-msg");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.className).toContain("border-bad");
    expect(input.className).not.toContain("border-line");
  });

  it("says nothing with neither message, so no row shifts", () => {
    const { container } = render(
      <Field label="Goal" id="goal" value="1000" onChange={vi.fn()} type="number" />,
    );
    const input = screen.getByLabelText("Goal");
    expect(input).not.toHaveAttribute("aria-describedby");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(container.querySelector("#goal-msg")).toBeNull();
  });

  it("passes the typing hints straight to the input", () => {
    render(
      <Field
        label="Port"
        id="port"
        value="5555"
        onChange={vi.fn()}
        inputMode="numeric"
        spellCheck={false}
        autoComplete="off"
      />,
    );
    const input = screen.getByLabelText("Port");
    expect(input).toHaveAttribute("inputmode", "numeric");
    expect(input).toHaveAttribute("spellcheck", "false");
    expect(input).toHaveAttribute("autocomplete", "off");
  });

  it("keeps the spellchecker off the masked token by default", () => {
    render(
      <Field
        label="Brawl Stars API token"
        id="token"
        value="a-token-that-is-not-real"
        onChange={vi.fn()}
        type="password"
      />,
    );
    expect(screen.getByLabelText("Brawl Stars API token")).toHaveAttribute("spellcheck", "false");
  });
});
