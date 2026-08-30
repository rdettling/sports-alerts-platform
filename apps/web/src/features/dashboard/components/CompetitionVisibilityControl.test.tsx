import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CompetitionVisibilityControl } from "./CompetitionVisibilityControl";

const apiMocks = vi.hoisted(() => ({
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

function renderControl() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CompetitionVisibilityControl
        token="token"
        competitions={competitions}
        visibility={{ hidden_competitions: ["WNBA"] }}
      />
    </QueryClientProvider>,
  );
  return client;
}

describe("CompetitionVisibilityControl", () => {
  beforeEach(() => {
    apiMocks.updateCompetitionVisibility.mockReset();
    apiMocks.updateCompetitionVisibility.mockImplementation(
      async (_token: string, hidden_competitions: string[]) => ({ hidden_competitions }),
    );
  });

  it("saves active choices while preserving hidden inactive competitions", async () => {
    const client = renderControl();
    fireEvent.click(screen.getByRole("button", { name: "Leagues" }));

    expect(screen.getByRole("dialog", { name: "Leagues shown" })).toHaveTextContent(
      "does not change your follows or alerts",
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "NBA" }));
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
    renderControl();
    fireEvent.click(screen.getByRole("button", { name: "Leagues" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "NBA" }));
    fireEvent.click(screen.getByRole("button", { name: "Show all" }));

    expect(screen.getByRole("checkbox", { name: "NBA" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();

    fireEvent.click(screen.getByRole("checkbox", { name: "College Football" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save");

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Leagues" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
