/**
 * The kit page's one guarantee: it renders on its own.
 *
 * No router and no query client are provided here on purpose. A Link or a query hook that
 * crept into the page would throw at mount, which is exactly the failure this catches:
 * the captures are taken against a dev server with no API behind it, so a kit that needs
 * either one is a kit that cannot be looked at. fetch is left undefined for the same
 * reason, so a request would throw rather than quietly resolve.
 */
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Kit } from "./Kit";
import { resetToasts } from "../lib/toast";

beforeEach(() => {
  resetToasts();
  vi.stubGlobal("fetch", () => {
    throw new Error("the kit page made a request");
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Kit", () => {
  it("mounts with no router, no query client and no request", () => {
    render(<Kit />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Component kit" }),
    ).toBeVisible();
  });

  it("shows every section the kit is meant to cover", () => {
    render(<Kit />);
    for (const title of [
      "Buttons",
      "Switches",
      "Fields",
      "Segmented",
      "Table",
      "Chips",
      "Toasts",
      "Text roles",
      "Radius",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: title }),
      ).toBeVisible();
    }
  });
});
