/** Where the wizard opens, what the rail may tick, and how walking forward and back
 * behaves. */
import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useSetupState } from "./useSetupState";
import type { AppSettings, ScanResponse } from "../api/types";
import { useSettingsPatch } from "../settings/useSettingsPatch";
import { makeSettings } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";
import { testQueryClient } from "../test/renderWithProviders";

const ADB = "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe";

function found(adbPath: string): ScanResponse {
  return { adb_path: adbPath, adb_found: true, conf_found: true, instances: [] };
}

function mount(settings: AppSettings) {
  stubFetch((url) => {
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    return jsonResponse(settings);
  });
  const client = testQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(
    () => {
      const settingsPatch = useSettingsPatch();
      return useSetupState(settingsPatch);
    },
    { wrapper },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useSetupState", () => {
  it("opens on BlueStacks when config.toml names no adb path", async () => {
    const blank = makeSettings({ instances: [] });
    blank.connection.adb_path = "";
    const { result } = mount(blank);
    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });
    expect(result.current.step).toBe("bluestacks");
    expect(result.current.index).toBe(0);
    expect(result.current.done.instances).toBe(false);
  });

  it("opens on BlueStacks with no fleet yet, and on Done once one is configured", async () => {
    const noFleet = makeSettings({ instances: [] });
    const first = mount(noFleet);
    await waitFor(() => {
      expect(first.result.current.ready).toBe(true);
    });
    // Nothing on disk names a fleet, so this is a fresh install and it starts at step 1.
    expect(first.result.current.step).toBe("bluestacks");
    first.unmount();
    vi.unstubAllGlobals();

    const configured = makeSettings();
    configured.connection.adb_path = ADB;
    const withFleet = mount(configured);
    await waitFor(() => {
      expect(withFleet.result.current.ready).toBe(true);
    });
    // A path and a fleet on disk mean the checks have been through here, so the return
    // visit opens on the last step, which offers to run them again.
    expect(withFleet.result.current.step).toBe("done");
    expect(withFleet.result.current.index).toBe(4);
    // Nothing about the display is stored, so it is never already done.
    expect(withFleet.result.current.done.display).toBe(false);
    expect(withFleet.result.current.done.instances).toBe(true);
    expect(withFleet.result.current.done.bluestacks).toBe(true);
    expect(withFleet.result.current.done.done).toBe(true);
  });

  it("ticks BlueStacks from the stored path and Display from this visit's check", async () => {
    const settings = makeSettings();
    settings.connection.adb_path = "";
    const { result } = mount(settings);
    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });
    expect(result.current.done.bluestacks).toBe(false);
    expect(result.current.done.display).toBe(false);

    act(() => {
      result.current.setScan(found("D:\\portable\\adb.exe"));
    });
    // The stored path is what the tick means now, and a scan has not written one.
    expect(result.current.done.bluestacks).toBe(false);

    act(() => {
      result.current.setDisplayPassed(true);
    });
    expect(result.current.done.display).toBe(true);
  });

  it("walks forward and back, and counts Stats done once it has been skipped", async () => {
    const settings = makeSettings();
    settings.connection.brawl_api_token = "";
    settings.instances = [{ name: "Pie64", adb_port: 5555, player_tag: "" }];
    const { result } = mount(settings);
    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });
    expect(result.current.step).toBe("done");
    act(() => {
      result.current.go("display");
    });
    expect(result.current.done.stats).toBe(false);

    act(() => {
      result.current.next();
    });
    expect(result.current.step).toBe("stats");
    act(() => {
      result.current.skipStats();
    });
    expect(result.current.done.stats).toBe(true);

    act(() => {
      result.current.next();
    });
    expect(result.current.step).toBe("done");
    expect(result.current.index).toBe(4);
    // The last step has nowhere further to go.
    act(() => {
      result.current.next();
    });
    expect(result.current.step).toBe("done");

    act(() => {
      result.current.back();
    });
    expect(result.current.step).toBe("stats");
    act(() => {
      result.current.go("bluestacks");
    });
    expect(result.current.step).toBe("bluestacks");
    act(() => {
      result.current.back();
    });
    expect(result.current.step).toBe("bluestacks");
  });
});
