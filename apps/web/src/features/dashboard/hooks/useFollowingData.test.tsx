import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useFollowingData } from "./useFollowingData";

vi.mock("../../../shared/api", () => ({
  listFollows: vi.fn(async () => ({ teams: [], games: [] })),
  listTeams: vi.fn(async () => []),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useFollowingData", () => {
  it("loads following data", async () => {
    const { result } = renderHook(() => useFollowingData("token"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.follows.teams).toHaveLength(0);
    expect(result.current.data?.follows.games).toHaveLength(0);
  });
});
