/** The rail: the wordmark, three sections with soon tags on the two that are not built,
 * and every instance with a dot in its state's colour. */
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
  it("shows the wordmark and tags the one section that is not built yet", async () => {
    stubInstances();
    renderWithProviders(<Rail />);
    expect(screen.getByText("brawlfarm")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fleet" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /Stats/ })).toHaveTextContent("Stats soon");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(await screen.findByText("Instances")).toBeInTheDocument();
  });

  it("gives every instance a dot in its state's tone", async () => {
    stubInstances();
    renderWithProviders(<Rail />);
    const pie64 = await screen.findByRole("link", { name: /Pie64$/ });
    expect(pie64).toHaveAttribute("href", "/instances/Pie64");
    expect(pie64.querySelector("[data-tone]")).toHaveAttribute("data-tone", "ok");
    expect(
      screen.getByRole("link", { name: /Pie64_1/ }).querySelector("[data-tone]"),
    ).toHaveAttribute("data-tone", "bad");
    expect(
      screen.getByRole("link", { name: /Pie64_3/ }).querySelector("[data-tone]"),
    ).toHaveAttribute("data-tone", "idle");
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
});
