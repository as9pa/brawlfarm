/** Failures the user can act on: the API's own sentence, the validation lines, or the
 * panel's wording when the server is gone. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ErrorBlock } from "./ErrorBlock";
import { ApiError } from "../../api/client";

describe("ErrorBlock", () => {
  it("prints the API's detail verbatim", () => {
    render(<ErrorBlock error={new ApiError(409, "Stop Pie64 before removing it")} />);
    expect(screen.getByText("Stop Pie64 before removing it")).toBeInTheDocument();
  });

  it("prints one line per validation error", () => {
    render(
      <ErrorBlock
        error={
          new ApiError(422, "Validation failed", [
            "body.goal_trophies: Input should be greater than or equal to 0",
          ])
        }
      />,
    );
    expect(screen.getByText("Validation failed")).toBeInTheDocument();
    expect(
      screen.getByText("body.goal_trophies: Input should be greater than or equal to 0"),
    ).toBeInTheDocument();
  });

  it("says the panel cannot reach the server when fetch itself failed", () => {
    render(
      <ErrorBlock error={new ApiError(0, "The panel cannot reach brawlfarm. Is it still running?")} />,
    );
    expect(
      screen.getByText("The panel cannot reach brawlfarm. Is it still running?"),
    ).toBeInTheDocument();
  });

  it("offers Retry only when it was given something to retry", async () => {
    const onRetry = vi.fn();
    const { rerender } = render(<ErrorBlock error={new ApiError(503, "adb did not answer")} />);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    rerender(<ErrorBlock error={new ApiError(503, "adb did not answer")} onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("copes with something that is not an ApiError at all", () => {
    render(<ErrorBlock error={new Error("boom")} />);
    expect(screen.getByText("boom")).toBeInTheDocument();
    render(<ErrorBlock error={{ weird: true }} />);
    expect(screen.getByText("Request failed")).toBeInTheDocument();
  });
});
