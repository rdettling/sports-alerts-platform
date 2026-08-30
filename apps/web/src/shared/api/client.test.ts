import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, isUnauthorizedError } from "./client";

describe("api client errors", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("preserves the response status for authentication decisions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Invalid token" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const error = await apiRequest("/auth/me", { token: "expired" }).catch(
      (requestError: unknown) => requestError,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Invalid token", status: 401 });
    expect(isUnauthorizedError(error)).toBe(true);
  });

  it("does not classify server errors as invalid sessions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Temporarily unavailable" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const error = await apiRequest("/auth/me", { token: "valid" }).catch(
      (requestError: unknown) => requestError,
    );

    expect(error).toMatchObject({ status: 503 });
    expect(isUnauthorizedError(error)).toBe(false);
  });
});
