import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthPage } from "./AuthPage";

const sendMagicLinkMock = vi.fn(async () => ({ message: "ok" }));
const verifyMagicLinkTokenMock = vi.fn(async () => {});
const warmAuthDbMock = vi.fn(async () => {});

vi.mock("./auth-context", () => ({
  useAuth: () => ({
    sendMagicLink: sendMagicLinkMock,
    verifyMagicLinkToken: verifyMagicLinkTokenMock,
  }),
}));

vi.mock("../../shared/api", () => ({
  warmAuthDb: () => warmAuthDbMock(),
}));

function renderAuthPage() {
  return render(
    <MemoryRouter initialEntries={["/auth"]}>
      <AuthPage />
    </MemoryRouter>,
  );
}

describe("AuthPage", () => {
  beforeEach(() => {
    sessionStorage.clear();
    sendMagicLinkMock.mockClear();
    verifyMagicLinkTokenMock.mockClear();
    warmAuthDbMock.mockClear();
  });

  it("warms DB once per tab session", () => {
    const first = renderAuthPage();
    expect(warmAuthDbMock).toHaveBeenCalledTimes(1);
    first.unmount();

    renderAuthPage();
    expect(warmAuthDbMock).toHaveBeenCalledTimes(1);
  });

  it("shows slow warmup hint when submit exceeds threshold", async () => {
    sendMagicLinkMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ message: "sent" }), 1500);
        }),
    );

    renderAuthPage();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));
    expect(sendMagicLinkMock).toHaveBeenCalledTimes(1);

    expect(
      await screen.findByText("Waking database, this may take a few seconds.", undefined, { timeout: 2500 }),
    ).toBeTruthy();
    await waitFor(() => expect(screen.queryByText("Waking database, this may take a few seconds.")).toBeNull());
  });
});
