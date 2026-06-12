import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useGamesData } from "./useGamesData";

vi.mock("../../../shared/api", () => ({
  listGames: vi.fn(async () => []),
  listFollows: vi.fn(async () => ({ teams: [], games: [] })),
  listTeams: vi.fn(async () => []),
  listAlertHistory: vi.fn(async () => ({ items: [] })),
  listLeagues: vi.fn(async () => [{ league: "NBA", is_enabled: true }]),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useGamesData", () => {
  it("loads dashboard data", async () => {
    const { result } = renderHook(() => useGamesData("token"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.sentAlerts24h).toBe(0);
  });
});
