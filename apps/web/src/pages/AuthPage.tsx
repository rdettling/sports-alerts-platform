import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth";

export function AuthPage() {
  const navigate = useNavigate();
  const { loginWithPassword, registerWithPassword } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        await loginWithPassword(email, password);
      } else {
        await registerWithPassword(email, password);
      }
      navigate("/games");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Auth request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container">
      <h1>Sports Alerts</h1>
      <p>Milestone 1 auth</p>
      <form onSubmit={onSubmit} className="card">
        <label>
          Email
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error ? <div className="error">{error}</div> : null}
        <button disabled={busy} type="submit">
          {busy ? "Working..." : mode === "login" ? "Login" : "Register"}
        </button>
      </form>
      <button className="link" onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Need an account? Register" : "Already have an account? Login"}
      </button>
    </div>
  );
}
