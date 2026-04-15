import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth";

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
    <div className="container">
      <h1>Sports Alerts</h1>
      <p>Email sign-in</p>
      <form onSubmit={onSubmit} className="card">
        <label>
          Email
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        {error ? <div className="error">{error}</div> : null}
        {info ? <p className="muted">{info}</p> : null}
        <button disabled={busy} type="submit">
          {busy ? "Working..." : tokenFromUrl ? "Verifying..." : "Send magic link"}
        </button>
      </form>
    </div>
  );
}
