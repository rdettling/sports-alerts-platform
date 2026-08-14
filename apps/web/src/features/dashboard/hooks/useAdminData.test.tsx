import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useAdminData } from "./useAdminData";

const getOpsAdminSummaryMock = vi.hoisted(() => vi.fn());

vi.mock("../../../shared/api", () => ({ getOpsAdminSummary: getOpsAdminSummaryMock }));

describe("useAdminData", () => {
  it("preserves previous data across window changes", async () => {
    const first = { overview: { window: "24h" } };
    let resolveSecond: ((value: unknown) => void) | undefined;
    getOpsAdminSummaryMock.mockResolvedValueOnce(first).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveSecond = resolve;
        }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result, rerender } = renderHook(
      ({ windowValue }) => useAdminData("token", windowValue),
      { wrapper, initialProps: { windowValue: "24h" as const } },
    );
    await waitFor(() => expect(result.current.data?.summary).toBe(first));
    rerender({ windowValue: "7d" as never });
    expect(result.current.data?.summary).toBe(first);
    expect(result.current.isFetching).toBe(true);

    resolveSecond?.({ overview: { window: "7d" } });
    await waitFor(() => expect(result.current.data?.summary.overview.window).toBe("7d"));
  });
});
