import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useGamesData } from "./useGamesData";

const apiMocks = vi.hoisted(() => ({
  listGames: vi.fn(async () => []),
  listFollows: vi.fn(async () => ({ teams: [], games: [] })),
  listTeams: vi.fn(async () => []),
  listCompetitions: vi.fn(async () => []),
}));

vi.mock("../../../shared/api", () => apiMocks);

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useGamesData", () => {
  beforeEach(() => {
    Object.values(apiMocks).forEach((mock) => mock.mockClear());
  });

  it("loads public data without requesting follows for a guest", async () => {
    const { result } = renderHook(() => useGamesData(null), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMocks.listGames).toHaveBeenCalled();
    expect(apiMocks.listTeams).toHaveBeenCalled();
    expect(apiMocks.listCompetitions).toHaveBeenCalled();
    expect(apiMocks.listFollows).not.toHaveBeenCalled();
    expect(result.current.data?.follows).toEqual({ teams: [], games: [] });
  });

  it("loads follows when authenticated", async () => {
    const { result } = renderHook(() => useGamesData("token"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMocks.listFollows).toHaveBeenCalledWith("token");
  });
});
