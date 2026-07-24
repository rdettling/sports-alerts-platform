import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignInModal } from "./SignInModal";

const sendMagicLinkMock = vi.fn(async () => ({ message: "Check your email." }));
const warmAuthDbMock = vi.fn(async () => {});
let currentUser: { email: string } | null = null;

vi.mock("./auth-context", () => ({
  useAuth: () => ({
    sendMagicLink: sendMagicLinkMock,
    user: currentUser,
  }),
}));

vi.mock("../../shared/api", () => ({
  warmAuthDb: () => warmAuthDbMock(),
}));

describe("SignInModal", () => {
  beforeEach(() => {
    sessionStorage.clear();
    currentUser = null;
    sendMagicLinkMock.mockClear();
    warmAuthDbMock.mockClear();
  });

  it("warms once and shows the check-email state after submitting", async () => {
    const onClose = vi.fn();
    const { rerender } = render(<SignInModal isOpen onClose={onClose} />);

    expect(warmAuthDbMock).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send magic link" }));

    await waitFor(() => expect(sendMagicLinkMock).toHaveBeenCalledWith("user@example.com"));
    expect(await screen.findByText("Check your email.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Use a different email" })).toBeInTheDocument();

    rerender(<SignInModal isOpen={false} onClose={onClose} />);
    rerender(<SignInModal isOpen onClose={onClose} />);
    expect(warmAuthDbMock).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape and when authentication completes", () => {
    const onClose = vi.fn();
    const { rerender } = render(<SignInModal isOpen onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    currentUser = { email: "user@example.com" };
    rerender(<SignInModal isOpen onClose={onClose} />);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
