import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthCallbackPage } from "./AuthCallbackPage";

const verifyMagicLinkTokenMock = vi.fn(async () => {});

vi.mock("./auth-context", () => ({
  useAuth: () => ({
    verifyMagicLinkToken: verifyMagicLinkTokenMock,
  }),
}));

function renderAuthCallbackPage(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/auth" element={<AuthCallbackPage />} />
        <Route path="/games" element={<div>Games view</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AuthCallbackPage", () => {
  beforeEach(() => {
    verifyMagicLinkTokenMock.mockReset();
    verifyMagicLinkTokenMock.mockResolvedValue(undefined);
  });

  it("redirects direct visits to games", async () => {
    renderAuthCallbackPage("/auth");
    expect(await screen.findByText("Games view")).toBeInTheDocument();
    expect(verifyMagicLinkTokenMock).not.toHaveBeenCalled();
  });

  it("verifies a magic link once and redirects to games", async () => {
    renderAuthCallbackPage("/auth?token=magic-token");

    await waitFor(() => expect(verifyMagicLinkTokenMock).toHaveBeenCalledTimes(1));
    expect(verifyMagicLinkTokenMock).toHaveBeenCalledWith("magic-token");
    expect(await screen.findByText("Games view")).toBeInTheDocument();
  });

  it("shows an error when verification fails", async () => {
    verifyMagicLinkTokenMock.mockRejectedValueOnce(new Error("Invalid or expired token"));
    renderAuthCallbackPage("/auth?token=bad-token");

    expect(await screen.findByText("Invalid or expired token")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to games" })).toBeInTheDocument();
  });
});
