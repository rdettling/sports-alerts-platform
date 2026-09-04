import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type CompetitionSetting } from "../../../../shared/api";
import { basketballCompetition as item, baseballCompetition } from "./admin-test-fixtures";
import { AdminLeaguesPanel } from "./AdminLeaguesPanel";

const updateOpsCompetitionSettingMock = vi.hoisted(() => vi.fn());

vi.mock("../../../../shared/api", async () => {
  const actual =
    await vi.importActual<typeof import("../../../../shared/api")>("../../../../shared/api");
  return { ...actual, updateOpsCompetitionSetting: updateOpsCompetitionSettingMock };
});

function renderPanel(items: CompetitionSetting[] = [item]) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  function panel(nextItems: CompetitionSetting[]) {
    return (
      <QueryClientProvider client={client}>
        <AdminLeaguesPanel token="token" items={nextItems} schedule={null} active />
      </QueryClientProvider>
    );
  }
  const view = render(panel(items));
  return {
    invalidate,
    rerenderItems: (nextItems: CompetitionSetting[]) => view.rerender(panel(nextItems)),
  };
}

describe("AdminLeaguesPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    updateOpsCompetitionSettingMock.mockResolvedValue({ ...item, is_enabled: false });
  });

  it("updates a competition and invalidates the affected views", async () => {
    const { invalidate } = renderPanel();
    expect(screen.getByText("Leagues")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Disable WNBA" }));

    await waitFor(() =>
      expect(updateOpsCompetitionSettingMock).toHaveBeenCalledWith("token", "WNBA", false),
    );
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(4));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["admin-page", "token"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["games"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["teams"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["competitions"] });
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
    expect(action).toHaveTextContent("Saving…");

    rejectUpdate?.(new Error("Competition update failed"));
    expect(await screen.findByText("Competition update failed")).toBeInTheDocument();
  });
  it("shows each league's sync and interval with inline actions and no details panel", () => {
    renderPanel([{ ...item, is_enabled: false }, baseballCompetition]);
    const list = within(screen.getByLabelText("League list"));
    expect(list.getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
      "Disable MLB",
      "Enable WNBA",
    ]);
    const mlb = within(list.getByRole("listitem", { name: "MLB" }));
    expect(mlb.getByText("Next live sync")).toBeVisible();
    expect(mlb.getByText("Schedule unavailable")).toBeVisible();
    expect(mlb.getByText("Live sync interval")).toBeVisible();
    expect(mlb.getByText("5m")).toBeVisible();
    const wnba = within(list.getByRole("listitem", { name: "WNBA" }));
    expect(wnba.getByText("Not scheduled")).toBeVisible();
    expect(wnba.getByText("2m")).toBeVisible();
    expect(screen.queryByRole("button", { name: /^Select/ })).toBeNull();
    expect(screen.queryByLabelText("League details")).toBeNull();
    expect(screen.queryByText("Last success")).toBeNull();
  });

  it("allows enabling the first league when all leagues are disabled", async () => {
    renderPanel([
      { ...item, is_enabled: false },
      { ...baseballCompetition, is_enabled: false },
    ]);
    expect(screen.getByText("No enabled leagues")).toBeVisible();
    expect(screen.queryByText(/^Catalog sync/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Enable WNBA" }));
    await waitFor(() =>
      expect(updateOpsCompetitionSettingMock).toHaveBeenCalledWith("token", "WNBA", true),
    );
  });

  it("handles an empty league list and renders rows when data arrives", () => {
    const { rerenderItems } = renderPanel([]);
    expect(screen.getByText("No leagues available.")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Enable|Disable/ })).toBeNull();
    rerenderItems([baseballCompetition]);
    expect(screen.getByRole("button", { name: "Disable MLB" })).toBeVisible();
  });

  it("keeps pending actions and errors associated with the affected league", async () => {
    let rejectUpdate!: (error: Error) => void;
    updateOpsCompetitionSettingMock.mockImplementation(
      () =>
        new Promise((_, reject) => {
          rejectUpdate = reject;
        }),
    );
    renderPanel([item, baseballCompetition]);
    fireEvent.click(screen.getByRole("button", { name: "Disable WNBA" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Disable WNBA" })).toHaveTextContent("Saving…"),
    );
    expect(screen.getByRole("button", { name: "Disable MLB" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Disable MLB" })).toHaveTextContent("Disable");
    rejectUpdate(new Error("WNBA update failed"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Disable MLB" })).toBeEnabled());
    expect(within(screen.getByRole("listitem", { name: "MLB" })).queryByRole("alert")).toBeNull();
    expect(
      within(screen.getByRole("listitem", { name: "WNBA" })).getByRole("alert"),
    ).toHaveTextContent("WNBA update failed");
    expect(screen.getByRole("button", { name: "Disable WNBA" })).toBeEnabled();
  });
});
