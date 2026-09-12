/** The one write path: it re-reads before it writes, it writes the whole document, two
 * quick changes queue instead of racing, a 422 lands under the field that caused it, and a
 * 409 reaches the caller with the API's own sentence. */
import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fieldError,
  saveSetting,
  saveSettingAsync,
  settingsFieldErrors,
  useDebouncedSave,
  useSettingsPatch,
} from "./useSettingsPatch";
import { ApiError } from "../api/client";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { testQueryClient } from "../test/renderWithProviders";

const SETTINGS = "/api/settings";

/** A settings route that remembers: GET serves what is stored, PUT stores the body and
 * echoes it, which is exactly what brawlfarm/api/settings_routes.py does. */
function server(options: { putStatus?: number; putDetail?: string } = {}) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url !== SETTINGS) throw new Error(`unstubbed request: ${url}`);
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
  const client = testQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, ...renderHook(() => useSettingsPatch(), { wrapper }) };
}

/** Every settings document this panel has sent, parsed. */
function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

/** Where in `calls` each PUT sits, so the GET in front of it can be checked. */
function putIndexes(calls: FetchCall[]): number[] {
  return calls.flatMap((call, index) => (call.init?.method === "PUT" ? [index] : []));
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("settingsFieldErrors", () => {
  it("splits one error into its loc and its message", () => {
    expect(settingsFieldErrors("connection.adb_path: file not found")).toEqual({
      fields: { "connection.adb_path": "file not found" },
      rest: [],
    });
  });

  it("splits the joined list pydantic produces", () => {
    expect(
      settingsFieldErrors(
        "app.port: Input should be less than 65536; instances.0.player_tag: player tag must be # followed by letters from 0289PYLQGRJCUV",
      ),
    ).toEqual({
      fields: {
        "app.port": "Input should be less than 65536",
        "instances.0.player_tag":
          "player tag must be # followed by letters from 0289PYLQGRJCUV",
      },
      rest: [],
    });
  });

  it("keeps a piece it cannot split, rather than dropping it", () => {
    // A sentence the API grows later still has to reach the reader, under the section
    // title instead of under a field.
    expect(settingsFieldErrors("instance names must be unique; app.port: too big")).toEqual({
      fields: { "app.port": "too big" },
      rest: ["instance names must be unique"],
    });
    expect(settingsFieldErrors("")).toEqual({ fields: {}, rest: [] });
  });
});

describe("fieldError", () => {
  it("shows the last segment of the loc, and nothing at all for a field with no error", () => {
    const errors = { "connection.adb_path": "file not found" };
    expect(fieldError(errors, "connection.adb_path")).toBe("adb_path: file not found");
    expect(fieldError(errors, "connection.brawl_api_token")).toBeUndefined();
  });
});

describe("useSettingsPatch", () => {
  it("re-reads, mutates and puts the whole document back", async () => {
    const { calls, current } = server();
    const { result, client } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });

    await act(async () => {
      await result.current.patch((draft) => {
        draft.behavior.gas_aware = false;
      });
    });

    const sent = puts(calls);
    expect(sent).toHaveLength(1);
    expect(sent[0].behavior.gas_aware).toBe(false);
    // The whole document goes, not one key: the API has no PATCH, and a partial PUT would
    // drop every section it did not send.
    expect(sent[0].notifications.ntfy_server).toBe("https://ntfy.sh");
    expect(sent[0].instances).toEqual([{ name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" }]);
    // The read in front of the write is a fresh GET, never the cached copy.
    expect(calls[putIndexes(calls)[0] - 1].init?.method).toBeUndefined();
    expect(current().behavior.gas_aware).toBe(false);
    expect(client.getQueryData(["settings"])).toEqual(current());
    expect(result.current.savedAt).toMatch(/^\d\d:\d\d$/);
    expect(result.current.fieldErrors).toEqual({});
    expect(result.current.pending).toBe(false);
  });

  it("queues two quick changes so the second reads what the first stored", async () => {
    const { calls, current } = server();
    const { result } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });

    await act(async () => {
      const first = result.current.patch((draft) => {
        draft.behavior.gas_aware = false;
      });
      const second = result.current.patch((draft) => {
        draft.behavior.bush_hide = true;
      });
      await Promise.all([first, second]);
    });

    const sent = puts(calls);
    expect(sent).toHaveLength(2);
    // The second patch read the document the first one saved, so neither flip is lost.
    expect(sent[1].behavior.gas_aware).toBe(false);
    expect(sent[1].behavior.bush_hide).toBe(true);
    expect(current().behavior).toMatchObject({ gas_aware: false, bush_hide: true });
    // No PUT overlapped another: the second one has its own GET immediately in front of it.
    expect(calls[putIndexes(calls)[1] - 1].init?.method).toBeUndefined();
  });

  it("invalidates the instances list only when the document's instances changed", async () => {
    server();
    const { result, client } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });
    const invalidate = vi.spyOn(client, "invalidateQueries");

    await act(async () => {
      await result.current.patch((draft) => {
        draft.app.theme = "dark";
      });
    });
    expect(invalidate.mock.calls.map((call) => call[0]?.queryKey)).toEqual([["settings"]]);

    invalidate.mockClear();
    await act(async () => {
      await result.current.patch((draft) => {
        draft.instances.push({ name: "Pie64_3", adb_port: 5585, player_tag: "" });
      });
    });
    // A new instance has to reach the rail and the Fleet grid, not just this screen.
    expect(invalidate.mock.calls.map((call) => call[0]?.queryKey)).toEqual([
      ["settings"],
      ["instances"],
    ]);
  });

  it("puts a 422 under its own field and leaves the stored document alone", async () => {
    const { calls, current } = server({
      putStatus: 422,
      putDetail: "connection.adb_path: file not found; instances.0.player_tag: bad tag",
    });
    const { result, client } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });
    const before = client.getQueryData(["settings"]);

    await act(async () => {
      await expect(
        result.current.patch((draft) => {
          draft.connection.adb_path = "D:/nope.exe";
        }),
      ).rejects.toBeInstanceOf(ApiError);
    });

    expect(result.current.fieldErrors).toEqual({
      "connection.adb_path": "file not found",
      "instances.0.player_tag": "bad tag",
    });
    expect(result.current.sectionErrors).toEqual([]);
    expect(fieldError(result.current.fieldErrors, "connection.adb_path")).toBe(
      "adb_path: file not found",
    );
    // The cache is left exactly as it was: the reader keeps looking at what is on disk.
    expect(client.getQueryData(["settings"])).toEqual(before);
    expect(current().connection.adb_path).toBe(makeSettings().connection.adb_path);
    expect(puts(calls)).toHaveLength(1);
  });

  it("hands a 409 to the caller with the API's own sentence", async () => {
    server({ putStatus: 409, putDetail: "Stop Pie64_3 before removing it" });
    const { result } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });

    let caught: unknown;
    await act(async () => {
      await result.current
        .patch((draft) => {
          draft.instances = [];
        })
        .catch((error: unknown) => {
          caught = error;
        });
    });

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(409);
    expect((caught as ApiError).detail).toBe("Stop Pie64_3 before removing it");
    // A refusal is not a validation error, so nothing goes under a field.
    expect(result.current.fieldErrors).toEqual({});
  });

  it("saveSetting toasts once the document is on disk, and is silent about a 422", async () => {
    server();
    const first = mount();
    await waitFor(() => {
      expect(first.result.current.settings).not.toBeUndefined();
    });
    const failures: unknown[] = [];
    saveSetting(
      first.result.current.patch,
      (draft) => {
        draft.scheduler.default_enabled = false;
      },
      (error: unknown) => failures.push(error),
    );
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Settings saved"]);
    });
    expect(failures).toEqual([]);
    first.unmount();
    resetToasts();
    vi.unstubAllGlobals();

    server({ putStatus: 422, putDetail: "app.port: Input should be less than 65536" });
    const second = mount();
    await waitFor(() => {
      expect(second.result.current.settings).not.toBeUndefined();
    });
    saveSetting(
      second.result.current.patch,
      (draft) => {
        draft.app.port = 99999;
      },
      (error: unknown) => failures.push(error),
    );
    await waitFor(() => {
      expect(second.result.current.fieldErrors).toEqual({
        "app.port": "Input should be less than 65536",
      });
    });
    // The message is already under app.port; an ErrorBlock saying it again would be the
    // second copy, and no toast is raised for a value that was never stored.
    expect(failures).toEqual([]);
    expect(toastMessages()).toEqual([]);
  });

  it("saveSettingAsync resolves on a save that landed and rejects on one that did not", async () => {
    server({ putStatus: 422, putDetail: "app.port: Input should be less than 65536" });
    const view = mount();
    await waitFor(() => {
      expect(view.result.current.settings).not.toBeUndefined();
    });
    const settled: string[] = [];
    await act(async () => {
      await saveSettingAsync(
        view.result.current.patch,
        (draft) => {
          draft.app.port = 99999;
        },
        () => settled.push("failure"),
      ).then(
        () => settled.push("resolved"),
        () => settled.push("rejected"),
      );
    });
    // Rejected, so the debounce keeps the typed text; and onFailure was not called,
    // because the message is already under app.port.
    expect(settled).toEqual(["rejected"]);
    expect(toastMessages()).toEqual([]);
  });
});

describe("useDebouncedSave", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("saves once the typing stops, and at once on blur", async () => {
    const saved: string[] = [];
    const save = (value: string): Promise<void> => {
      saved.push(value);
      return Promise.resolve();
    };
    const { result } = renderHook(() => useDebouncedSave("1600", save));
    expect(result.current.value).toBe("1600");

    act(() => {
      result.current.onChange("9");
    });
    act(() => {
      result.current.onChange("90");
    });
    expect(result.current.value).toBe("90");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(499);
    });
    expect(saved).toEqual([]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(saved).toEqual(["90"]);
    // Once the save lands the box shows what is on disk again, not what was typed: the
    // model may have normalised it on the way through.
    expect(result.current.value).toBe("1600");

    act(() => {
      result.current.onChange("900");
    });
    await act(async () => {
      result.current.onBlur();
      await vi.advanceTimersByTimeAsync(0);
    });
    // Leaving the box does not wait out the rest of the debounce.
    expect(saved).toEqual(["90", "900"]);
  });

  it("does nothing on a blur with nothing pending", () => {
    const saved: string[] = [];
    const { result } = renderHook(() =>
      useDebouncedSave("1600", (value) => {
        saved.push(value);
        return Promise.resolve();
      }),
    );
    act(() => {
      result.current.onBlur();
    });
    expect(saved).toEqual([]);
  });
});
