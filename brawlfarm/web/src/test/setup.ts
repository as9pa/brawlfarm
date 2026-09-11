/**
 * Runs before every test file: the jest-dom matchers (toBeInTheDocument, toHaveAttribute)
 * and an unmount after each test, so one test's DOM never leaks into the next.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
