import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CompetitionVisibilityModal } from "./CompetitionVisibilityModal";

const apiMocks = vi.hoisted(() => ({
  getCompetitionVisibility: vi.fn(),
  listCompetitions: vi.fn(),
  updateCompetitionVisibility: vi.fn(),
}));

vi.mock("../../../shared/api", () => apiMocks);

const competitions = [
  {
    competition: "NBA" as const,
    sport: "basketball" as const,
    label: "NBA",
    badge_label: "NBA",
    alert_types: [],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
  {
    competition: "FBS" as const,
    sport: "football" as const,
    label: "College Football",
    badge_label: "FBS",
    alert_types: [],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
];

function ModalHarness() {
  const [isOpen, setIsOpen] = useState(true);
  return (
    <>
      <button type="button" onClick={() => setIsOpen(true)}>
        Open leagues
      </button>
      <CompetitionVisibilityModal isOpen={isOpen} token="token" onClose={() => setIsOpen(false)} />
    </>
  );
}

function renderModal() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModalHarness />
    </QueryClientProvider>,
  );
  return client;
}

describe("CompetitionVisibilityModal", () => {
  beforeEach(() => {
    apiMocks.getCompetitionVisibility.mockReset();
    apiMocks.listCompetitions.mockReset();
    apiMocks.updateCompetitionVisibility.mockReset();
    apiMocks.getCompetitionVisibility.mockResolvedValue({ hidden_competitions: ["WNBA"] });
    apiMocks.listCompetitions.mockResolvedValue(competitions);
    apiMocks.updateCompetitionVisibility.mockImplementation(
      async (_token: string, hidden_competitions: string[]) => ({ hidden_competitions }),
    );
  });

  it("loads preferences and saves active choices while preserving hidden inactive competitions", async () => {
    const client = renderModal();

    expect(screen.getByRole("status")).toHaveTextContent("Loading leagues...");
    expect(await screen.findByRole("dialog", { name: "Leagues shown" })).toHaveTextContent(
      "does not change your follows or alerts",
    );
    fireEvent.click(await screen.findByRole("checkbox", { name: "NBA" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(apiMocks.updateCompetitionVisibility).toHaveBeenCalledWith("token", ["WNBA", "NBA"]),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(client.getQueryData(["competition-visibility", "token"])).toEqual({
      hidden_competitions: ["WNBA", "NBA"],
    });
  });

  it("supports show all, cancel, Escape, and mutation errors", async () => {
    apiMocks.updateCompetitionVisibility.mockRejectedValueOnce(new Error("Could not save"));
    renderModal();
    fireEvent.click(await screen.findByRole("checkbox", { name: "NBA" }));
    fireEvent.click(screen.getByRole("button", { name: "Show all" }));

    expect(screen.getByRole("checkbox", { name: "NBA" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();

    fireEvent.click(screen.getByRole("checkbox", { name: "College Football" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save");

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Open leagues" }));
    await screen.findByRole("checkbox", { name: "NBA" });
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows query failures and retries both preference dependencies", async () => {
    apiMocks.listCompetitions
      .mockRejectedValueOnce(new Error("Could not load leagues"))
      .mockResolvedValueOnce(competitions);
    renderModal();

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load leagues");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByRole("checkbox", { name: "NBA" })).toBeChecked();
    expect(apiMocks.listCompetitions).toHaveBeenCalledTimes(2);
    expect(apiMocks.getCompetitionVisibility).toHaveBeenCalledTimes(2);
  });
});
