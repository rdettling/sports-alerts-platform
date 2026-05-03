import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "./auth-context";

export function AuthPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { sendMagicLink, verifyMagicLinkToken } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const tokenFromUrl = searchParams.get("token");

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
    setBusy(true);
    try {
      const response = await sendMagicLink(email);
      setInfo(response.message);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Auth request failed");
    } finally {
      setBusy(false);
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
        </form>
      </section>
    </div>
  );
}
