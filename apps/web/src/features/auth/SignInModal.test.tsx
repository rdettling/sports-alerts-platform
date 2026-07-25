import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignInModal } from "./SignInModal";

const sendMagicLinkMock = vi.fn(async () => ({ message: "Check your email." }));
const verifyMagicCodeMock = vi.fn(async () => {});
const warmAuthDbMock = vi.fn(async () => {});
let currentUser: { email: string } | null = null;

vi.mock("./auth-context", () => ({
  useAuth: () => ({
    sendMagicLink: sendMagicLinkMock,
    verifyMagicCode: verifyMagicCodeMock,
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
    verifyMagicCodeMock.mockReset();
    verifyMagicCodeMock.mockResolvedValue(undefined);
    warmAuthDbMock.mockClear();
    Object.defineProperty(navigator, "standalone", { configurable: true, value: false });
  });

  it("warms once and shows the check-email state after submitting", async () => {
    const onClose = vi.fn();
    const { rerender } = render(<SignInModal isOpen onClose={onClose} />);

    expect(warmAuthDbMock).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in email" }));

    await waitFor(() => expect(sendMagicLinkMock).toHaveBeenCalledWith("user@example.com"));
    expect(await screen.findByText("Check your email.")).toBeInTheDocument();
    expect(screen.getByLabelText("Sign-in code")).toHaveAttribute("autocomplete", "one-time-code");
    expect(screen.getByRole("button", { name: "Use a different email" })).toBeInTheDocument();

    rerender(<SignInModal isOpen={false} onClose={onClose} />);
    rerender(<SignInModal isOpen onClose={onClose} />);
    expect(warmAuthDbMock).toHaveBeenCalledTimes(1);
  });

  it("normalizes a pasted code and verifies it for the submitted email", async () => {
    render(<SignInModal isOpen onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in email" }));
    const codeInput = await screen.findByLabelText("Sign-in code");
    fireEvent.change(codeInput, { target: { value: "12a 3456" } });
    expect(codeInput).toHaveValue("123456");
    fireEvent.click(screen.getByRole("button", { name: "Verify code" }));

    await waitFor(() =>
      expect(verifyMagicCodeMock).toHaveBeenCalledWith("user@example.com", "123456"),
    );
  });

  it("keeps the code form usable after verification fails", async () => {
    verifyMagicCodeMock.mockRejectedValueOnce(new Error("Invalid or expired sign-in credential"));
    render(<SignInModal isOpen onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in email" }));
    fireEvent.change(await screen.findByLabelText("Sign-in code"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Verify code" }));

    expect(await screen.findByText("Invalid or expired sign-in credential")).toBeInTheDocument();
    expect(screen.getByLabelText("Sign-in code")).toHaveValue("123456");
  });

  it("explains Safari handoff in an installed Home Screen app", async () => {
    Object.defineProperty(navigator, "standalone", { configurable: true, value: true });
    render(<SignInModal isOpen onClose={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send sign-in email" }));

    expect(await screen.findByText(/Opening its link signs in Safari/)).toBeInTheDocument();
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
