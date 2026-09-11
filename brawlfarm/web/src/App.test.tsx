/** The scaffold end to end: React renders, the JSX transform runs, jsdom and the jest-dom
 * matchers are wired up. Task 4 replaces this with the routed shell's tests. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the wordmark", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "brawlfarm" })).toBeInTheDocument();
  });
});
