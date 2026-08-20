import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type CompetitionSetting } from "../../../../shared/api";
import { AdminCompetitionSettingsPanel } from "./AdminCompetitionSettingsPanel";

const updateOpsCompetitionSettingMock = vi.hoisted(() => vi.fn());

vi.mock("../../../../shared/api", async () => {
  const actual =
    await vi.importActual<typeof import("../../../../shared/api")>("../../../../shared/api");
  return { ...actual, updateOpsCompetitionSetting: updateOpsCompetitionSettingMock };
});

const item: CompetitionSetting = {
  competition: "WNBA",
  sport: "basketball",
  label: "WNBA",
  badge_label: "WNBA",
  alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
  live_sync_interval_seconds: 120,
  is_enabled: true,
};

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(
    <QueryClientProvider client={client}>
      <AdminCompetitionSettingsPanel token="token" items={[item]} />
    </QueryClientProvider>,
  );
  return { invalidate };
}

describe("AdminCompetitionSettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateOpsCompetitionSettingMock.mockResolvedValue({ ...item, is_enabled: false });
  });

  it("updates a competition and invalidates the affected views", async () => {
    const { invalidate } = renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Disable WNBA" }));

    await waitFor(() =>
      expect(updateOpsCompetitionSettingMock).toHaveBeenCalledWith("token", "WNBA", false),
    );
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(3));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["admin-page", "token"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["games-page", "token"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["teams-page", "token"] });
  });

  it("shows saving and error states", async () => {
    let rejectUpdate: ((error: Error) => void) | undefined;
    updateOpsCompetitionSettingMock.mockImplementation(
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

    rejectUpdate?.(new Error("Competition update failed"));
    expect(await screen.findByText("Competition update failed")).toBeInTheDocument();
  });
});
