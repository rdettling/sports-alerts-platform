import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { warmAuthDb } from "../../shared/api";
import { useAuth } from "./auth-context";

const AUTH_WARM_SESSION_KEY = "sports_alerts_auth_warm_v1";
const SLOW_HINT_THRESHOLD_MS = 1200;

export function AuthPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { sendMagicLink, verifyMagicLinkToken } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSlowHint, setShowSlowHint] = useState(false);

  const tokenFromUrl = searchParams.get("token");

  useEffect(() => {
    if (sessionStorage.getItem(AUTH_WARM_SESSION_KEY) === "1") {
      return;
    }
    sessionStorage.setItem(AUTH_WARM_SESSION_KEY, "1");
    warmAuthDb().catch(() => {
      // Warmup is best effort; auth flow should still work without it.
    });
  }, []);

  useEffect(() => {
    const run = async () => {
      if (!tokenFromUrl) {
        return;
      }
      setError(null);
      setInfo(null);
      setBusy(true);
      try {
        await verifyMagicLinkToken(tokenFromUrl);
        navigate("/games", { replace: true });
      } catch (verifyError) {
        setError(verifyError instanceof Error ? verifyError.message : "Magic link verification failed");
      } finally {
        setBusy(false);
      }
    };
    run();
  }, [navigate, tokenFromUrl, verifyMagicLinkToken]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setInfo(null);
    setShowSlowHint(false);
    setBusy(true);
    const timer = window.setTimeout(() => setShowSlowHint(true), SLOW_HINT_THRESHOLD_MS);
    try {
      const response = await sendMagicLink(email);
      setInfo(response.message);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Auth request failed");
    } finally {
      window.clearTimeout(timer);
      setBusy(false);
      setShowSlowHint(false);
    }
  };

  return (
    <div className="auth-page">
      <section className="auth-shell">
        <p className="auth-kicker">Welcome</p>
        <h1>Live Game Alerts</h1>
        <p className="auth-subtitle">Sign in with your email to manage follows and alerts.</p>
        <form onSubmit={onSubmit} className="auth-card">
          <label className="auth-label" htmlFor="email">
            Email
          </label>
          <div className="auth-row">
            <input
              id="email"
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
            <button disabled={busy} type="submit">
              {busy ? "Working..." : tokenFromUrl ? "Verifying..." : "Send magic link"}
            </button>
          </div>
          {error ? <div className="error">{error}</div> : null}
          {info ? <p className="muted">{info}</p> : null}
          {busy && showSlowHint && !tokenFromUrl ? <p className="muted">Waking database, this may take a few seconds.</p> : null}
        </form>
      </section>
    </div>
  );
}
