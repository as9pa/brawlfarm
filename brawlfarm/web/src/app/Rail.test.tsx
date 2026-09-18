/** The rail: the wordmark, four sections, none of them tagged as unbuilt any more, and
 * every instance named in words beside the state it is in. */
import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Rail } from "./Rail";
import { jsonResponse, stubFetch } from "../test/http";
import { makeInstance } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubInstances(): void {
  stubFetch(() =>
    jsonResponse({
      instances: [
        makeInstance({ name: "Pie64", state: "farming" }),
        makeInstance({ name: "Pie64_1", adb_port: 5565, state: "offline" }),
        makeInstance({ name: "Pie64_3", adb_port: 5585, state: "scheduled_break" }),
      ],
    }),
  );
}

describe("Rail", () => {
  it("shows the wordmark and no longer tags any section as unbuilt", async () => {
    stubInstances();
    renderWithProviders(<Rail />);
    expect(screen.getByText("brawlfarm")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fleet" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Stats" })).toHaveAttribute("href", "/stats");
    expect(screen.getByRole("link", { name: "Calibration" })).toHaveAttribute(
      "href",
      "/calibration",
    );
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.queryByText("soon")).toBeNull();
    expect(await screen.findByText("Instances")).toBeInTheDocument();
  });

  it("names every instance and says its state in words", async () => {
    stubInstances();
    renderWithProviders(<Rail />);
    const pie64 = await screen.findByRole("link", { name: "Pie64 Farming" });
    expect(pie64).toHaveAttribute("href", "/instances/Pie64");
    expect(pie64.querySelector("[data-tone]")).toHaveAttribute("data-tone", "ok");
    expect(
      screen.getByRole("link", { name: "Pie64_1 Offline" }).querySelector("[data-tone]"),
    ).toHaveAttribute("data-tone", "bad");
    expect(
      screen.getByRole("link", { name: "Pie64_3 Scheduled break" }).querySelector("[data-tone]"),
    ).toHaveAttribute("data-tone", "idle");
  });

  it("lets a long instance name shrink rather than push the chip out", async () => {
    // jsdom lays nothing out, so the class is the only evidence there is: without
    // min-w-0 a flex item will not shrink below its content and truncate never fires.
    stubInstances();
    renderWithProviders(<Rail />);
    const name = await screen.findByText("Pie64");
    expect(name.className).toContain("min-w-0");
    expect(name.className).toContain("truncate");
  });

  it("sets nothing in the rail in mono", async () => {
    stubInstances();
    const { container } = renderWithProviders(<Rail />);
    await screen.findByRole("link", { name: "Pie64 Farming" });
    expect(container.querySelector(".font-mono")).toBeNull();
  });

  it("marks the page you are on", async () => {
    stubInstances();
    renderWithProviders(<Rail />, { route: "/instances/Pie64_1" });
    expect(await screen.findByRole("link", { name: /Pie64_1/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Fleet" })).not.toHaveAttribute("aria-current");
  });

  it("carries the shared focus ring on its links", async () => {
    stubInstances();
    renderWithProviders(<Rail />);
    expect((await screen.findByRole("link", { name: "Fleet" })).className).toContain(
      "focus-visible:outline-accent",
    );
  });
});
