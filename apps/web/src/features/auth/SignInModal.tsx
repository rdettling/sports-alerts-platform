import { FormEvent, useEffect, useState } from "react";

import { warmAuthDb } from "../../shared/api";
import { useAuth } from "./auth-context";

const AUTH_WARM_SESSION_KEY = "sports_alerts_auth_warm_v1";
const SLOW_HINT_THRESHOLD_MS = 1200;

type SignInModalProps = {
  isOpen: boolean;
  onClose: () => void;
};

export function SignInModal({ isOpen, onClose }: SignInModalProps) {
  const { sendMagicLink, verifyMagicCode, user } = useAuth();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSlowHint, setShowSlowHint] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setEmail("");
      setCode("");
      setError(null);
      setInfo(null);
      setBusy(false);
      setShowSlowHint(false);
      return;
    }

    if (sessionStorage.getItem(AUTH_WARM_SESSION_KEY) !== "1") {
      sessionStorage.setItem(AUTH_WARM_SESSION_KEY, "1");
      warmAuthDb().catch(() => undefined);
    }

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen && user) onClose();
  }, [isOpen, onClose, user]);

  if (!isOpen) return null;

  const isStandalone =
    (navigator as Navigator & { standalone?: boolean }).standalone === true ||
    window.matchMedia?.("(display-mode: standalone)").matches === true;

  const onSubmitEmail = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setShowSlowHint(false);
    setBusy(true);
    const timer = window.setTimeout(() => setShowSlowHint(true), SLOW_HINT_THRESHOLD_MS);
    try {
      const response = await sendMagicLink(email);
      setInfo(response.message);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-in request failed");
    } finally {
      window.clearTimeout(timer);
      setBusy(false);
      setShowSlowHint(false);
    }
  };

  const onSubmitCode = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verifyMagicCode(email, code);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Code verification failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="overlay-sheet" role="dialog" aria-modal="true" aria-labelledby="sign-in-title">
      <section className="overlay-card sign-in-modal">
        <header className="overlay-card-header">
          <div>
            <h4 id="sign-in-title">Sign in</h4>
            <p className="muted sign-in-modal-subtitle">
              Sign in to follow games and receive alerts.
            </p>
          </div>
          <button className="btn btn-secondary" type="button" onClick={onClose}>
            Close
          </button>
        </header>

        {info ? (
          <>
            <p>{info}</p>
            <p className="muted">
              {isStandalone
                ? "Enter the 6-digit code from the email below. Opening its link signs in Safari instead of this Home Screen app."
                : "Open the link in your email or enter its 6-digit code below."}
            </p>
            <form onSubmit={onSubmitCode} className="sign-in-modal-form">
              <label htmlFor="sign-in-code">Sign-in code</label>
              <input
                id="sign-in-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                placeholder="123456"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                autoFocus
                required
              />
              <button className="btn" disabled={busy || code.length !== 6} type="submit">
                {busy ? "Verifying..." : "Verify code"}
              </button>
              {error ? <p className="error">{error}</p> : null}
            </form>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => {
                setInfo(null);
                setCode("");
                setError(null);
              }}
            >
              Use a different email
            </button>
          </>
        ) : (
          <form onSubmit={onSubmitEmail} className="sign-in-modal-form">
            <label htmlFor="sign-in-email">Email</label>
            <input
              id="sign-in-email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoFocus
              required
            />
            <button className="btn" disabled={busy} type="submit">
              {busy ? "Working..." : "Send sign-in email"}
            </button>
            {error ? <p className="error">{error}</p> : null}
            {busy && showSlowHint ? (
              <p className="muted">Waking database, this may take a few seconds.</p>
            ) : null}
          </form>
        )}
      </section>
    </div>
  );
}
