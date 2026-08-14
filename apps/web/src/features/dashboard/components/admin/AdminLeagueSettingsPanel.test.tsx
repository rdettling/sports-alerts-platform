import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type LeagueSetting } from "../../../../shared/api";
import { AdminLeagueSettingsPanel } from "./AdminLeagueSettingsPanel";

const updateOpsLeagueSettingMock = vi.hoisted(() => vi.fn());

vi.mock("../../../../shared/api", async () => {
  const actual =
    await vi.importActual<typeof import("../../../../shared/api")>("../../../../shared/api");
  return { ...actual, updateOpsLeagueSetting: updateOpsLeagueSettingMock };
});

const item: LeagueSetting = {
  league: "WNBA",
  sport: "basketball",
  label: "WNBA",
  badge_label: "WNBA",
  alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
  live_sync_interval_seconds: 120,
  default_test_matchup: ["NY", "LV"],
  is_enabled: true,
};

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(
    <QueryClientProvider client={client}>
      <AdminLeagueSettingsPanel token="token" items={[item]} />
    </QueryClientProvider>,
  );
  return { invalidate };
}

describe("AdminLeagueSettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateOpsLeagueSettingMock.mockResolvedValue({ ...item, is_enabled: false });
  });

  it("updates a league and invalidates the affected views", async () => {
    const { invalidate } = renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Disable WNBA" }));

    await waitFor(() =>
      expect(updateOpsLeagueSettingMock).toHaveBeenCalledWith("token", "WNBA", false),
    );
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(3));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["admin-page", "token"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["games-page", "token"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["teams-page", "token"] });
  });

  it("shows saving and error states", async () => {
    let rejectUpdate: ((error: Error) => void) | undefined;
    updateOpsLeagueSettingMock.mockImplementation(
      () =>
        new Promise((_, reject) => {
          rejectUpdate = reject;
        }),
    );
    renderPanel();

    const action = screen.getByRole("button", { name: "Disable WNBA" });
    fireEvent.click(action);
    await waitFor(() => expect(action).toBeDisabled());
    expect(action).toHaveTextContent("Saving...");

    rejectUpdate?.(new Error("League update failed"));
    expect(await screen.findByText("League update failed")).toBeInTheDocument();
  });
});
