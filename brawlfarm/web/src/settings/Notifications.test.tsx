/** Settings > Notifications: four channels, seven events and one test send. */
import { fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const TEST_ROUTE = "/api/notifications/test";

function server(
  options: {
    settings?: AppSettings;
    sent?: string[];
    failed?: string[];
    testStatus?: number;
    testDetail?: string;
    putStatus?: number;
    putDetail?: string;
  } = {},
) {
  let stored = options.settings ?? makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url === TEST_ROUTE) {
      if (options.testStatus !== undefined) {
        return jsonResponse({ detail: options.testDetail }, options.testStatus);
      }
      return jsonResponse({ sent: options.sent ?? [], failed: options.failed ?? [] });
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/notifications" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Notifications", () => {
  it("lists the four channels in order with their sentences, and saves one on blur", async () => {
    const { calls, current } = server();
    mount();
    const topic = await screen.findByLabelText("ntfy topic");
    expect(
      screen.getByText(
        "Free phone notifications. Install the ntfy app, pick a topic name, type it here.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("ntfy server")).toHaveValue("https://ntfy.sh");
    expect(
      screen.getByText("Leave this unless you run your own ntfy server."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Webhook URL")).toBeInTheDocument();
    expect(
      screen.getByText(
        "A URL that receives each alert as a message, for chat apps that offer incoming webhooks.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Healthchecks URL")).toBeInTheDocument();
    expect(
      screen.getByText(
        "A check-in URL from healthchecks.io; it warns you when brawlfarm stops checking in.",
      ),
    ).toBeInTheDocument();

    fireEvent.change(topic, { target: { value: "brawlfarm-home" } });
    fireEvent.blur(topic);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].notifications.ntfy_topic).toBe("brawlfarm-home");
    expect(current().notifications.ntfy_topic).toBe("brawlfarm-home");
    expect(toastMessages()).toEqual(["Settings saved"]);
  });

  it("keeps the event list in the brief's order however it is ticked", async () => {
    const { calls } = server();
    mount();
    expect(await screen.findByText("Send me")).toBeInTheDocument();
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.map((box) => box.getAttribute("aria-label") ?? "")).toEqual([
      "Crash",
      "Recovery",
      "Instance offline",
      "Wrong mode",
      "Recalibration needed",
      "Stopped",
      "Wrong resolution",
    ]);
    // The fixture's default five are on; Stopped and Wrong resolution are not.
    expect(screen.getByRole("checkbox", { name: "Crash" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Stopped" })).not.toBeChecked();

    await userEvent.click(screen.getByRole("checkbox", { name: "Stopped" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    // Stored in the list's own order, not in the order they were clicked, so the file on
    // disk reads the same whatever route got it there.
    expect(puts(calls)[0].notifications.events).toEqual([
      "crash",
      "recover",
      "offline",
      "wrong_mode",
      "recalibrate",
      "stop",
    ]);

    await userEvent.click(screen.getByRole("checkbox", { name: "Crash" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(2);
    });
    expect(puts(calls)[1].notifications.events).toEqual([
      "recover",
      "offline",
      "wrong_mode",
      "recalibrate",
      "stop",
    ]);
  });

  it("will not send a test with no channel set, and says what to add first", async () => {
    // The fixture is the model default: no topic, no webhook, no healthchecks URL.
    const { calls } = server();
    mount();
    const button = await screen.findByRole("button", { name: "Send a test" });
    expect(button).toBeDisabled();
    expect(screen.getByText("Add a channel first")).toBeInTheDocument();

    await userEvent.click(button);
    expect(calls.filter((call) => call.url === TEST_ROUTE)).toHaveLength(0);
    expect(toastMessages()).toEqual([]);
  });

  it("puts a refused channel under the row that carried it", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "notifications.ntfy_topic: topic may not contain a slash",
    });
    mount();
    const topic = await screen.findByLabelText("ntfy topic");
    fireEvent.change(topic, { target: { value: "home/phone" } });
    fireEvent.blur(topic);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("ntfy_topic: topic may not contain a slash"),
    ).toBeInTheDocument();
    // The box keeps what is being fixed, and no toast claims it was saved.
    expect(topic).toHaveValue("home/phone");
    expect(toastMessages()).toEqual([]);
  });

  it("toasts what was sent and what failed, sent first", async () => {
    const withChannel = makeSettings();
    withChannel.notifications.ntfy_topic = "brawlfarm-home";
    const { calls } = server({ settings: withChannel, sent: ["ntfy"], failed: ["webhook"] });
    mount();
    const button = await screen.findByRole("button", { name: "Send a test" });
    expect(button).toBeEnabled();
    expect(screen.queryByText("Add a channel first")).not.toBeInTheDocument();

    await userEvent.click(button);
    await waitFor(() => {
      expect(calls.filter((call) => call.url === TEST_ROUTE)).toHaveLength(1);
    });
    expect(calls.find((call) => call.url === TEST_ROUTE)?.init?.method).toBe("POST");
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Test sent to ntfy", "Test failed for webhook"]);
    });
    // Nothing was saved: a test send writes no settings.
    expect(puts(calls)).toHaveLength(0);
  });
});
