/** The quiet strip that says why there are no per-game numbers, in the spec's own
 * sentences, with the link that fixes it. */
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConnectionStrip } from "./ConnectionStrip";
import { renderWithProviders } from "../test/renderWithProviders";

describe("ConnectionStrip", () => {
  it("renders nothing when the connection is ok", () => {
    const { container } = renderWithProviders(
      <ConnectionStrip status="ok" instanceWithoutTag={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("asks for a token, in warn, linking to Settings, Connection", () => {
    renderWithProviders(<ConnectionStrip status="no_token" instanceWithoutTag={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Battle log unavailable. Add a Brawl Stars API token in Settings to see per-game stats.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warn");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute(
      "href",
      "/settings/connection",
    );
  });

  it("asks for a player tag, naming the instance", () => {
    renderWithProviders(<ConnectionStrip status="no_tag" instanceWithoutTag="Pie64" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Add a player tag for Pie64 in Settings, Instances to see its games.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warn");
    expect(screen.getByRole("link", { name: "Settings, Instances" })).toHaveAttribute(
      "href",
      "/settings/instances",
    );
  });

  it("says nothing about a tag when there is no instance to name", () => {
    const { container } = renderWithProviders(
      <ConnectionStrip status="no_tag" instanceWithoutTag={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("reports a rejected token in bad, linking to Settings, Connection", () => {
    renderWithProviders(<ConnectionStrip status="rejected" instanceWithoutTag={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "The Brawl Stars API rejected the token. Check the token, and the IP address it was created for, in Settings, Connection.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "bad");
    expect(screen.getByRole("link", { name: "Settings, Connection" })).toHaveAttribute(
      "href",
      "/settings/connection",
    );
  });

  it("reports an unreachable API in warn, with no link", () => {
    renderWithProviders(<ConnectionStrip status="unreachable" instanceWithoutTag={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "The Brawl Stars API did not answer. Stats show what was logged so far.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warn");
    expect(screen.queryByRole("link")).toBeNull();
  });
});
