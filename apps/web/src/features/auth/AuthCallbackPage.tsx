import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { useAuth } from "./auth-context";

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { verifyMagicLinkToken } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const verificationStarted = useRef(false);

  const tokenFromUrl = searchParams.get("token");

  useEffect(() => {
    if (!tokenFromUrl || verificationStarted.current) return;
    verificationStarted.current = true;
    verifyMagicLinkToken(tokenFromUrl)
      .then(() => navigate("/", { replace: true }))
      .catch((verifyError) => {
        setError(
          verifyError instanceof Error ? verifyError.message : "Magic link verification failed",
        );
      });
  }, [navigate, tokenFromUrl, verifyMagicLinkToken]);

  if (!tokenFromUrl) return <Navigate to="/" replace />;

  return (
    <div className="container">
      <section className="auth-callback-card">
        <h1>Live Game Alerts</h1>
        {error ? (
          <>
            <p className="error" role="alert">
              {error}
            </p>
            <button className="btn" type="button" onClick={() => navigate("/", { replace: true })}>
              Back to games
            </button>
          </>
        ) : (
          <p role="status">Verifying your magic link...</p>
        )}
      </section>
    </div>
  );
}
