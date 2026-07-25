import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  deletePushSubscription,
  me,
  startMagicLink,
  verifyMagicLink,
  type UserProfile,
} from "../../shared/api";
import {
  getCurrentPushSubscription,
  pushSubscriptionPayload,
} from "../../shared/lib/push-notifications";

type AuthContextType = {
  isLoading: boolean;
  token: string | null;
  user: UserProfile | null;
  sendMagicLink: (email: string) => Promise<{ message: string }>;
  verifyMagicLinkToken: (token: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const AUTH_TOKEN_KEY = "sports_alerts_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [token, setToken] = useState<string | null>(localStorage.getItem(AUTH_TOKEN_KEY));
  const [user, setUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      if (!token) {
        setUser(null);
        setIsLoading(false);
        return;
      }
      try {
        const profile = await me(token);
        if (!cancelled) setUser(profile);
      } catch {
        if (!cancelled) {
          localStorage.removeItem(AUTH_TOKEN_KEY);
          setToken(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    const syncToken = (event: StorageEvent) => {
      if (event.storageArea !== localStorage || event.key !== AUTH_TOKEN_KEY) {
        return;
      }
      setToken(event.newValue);
      if (!event.newValue) {
        setUser(null);
      }
    };

    window.addEventListener("storage", syncToken);
    return () => window.removeEventListener("storage", syncToken);
  }, []);

  const sendMagicLink = useCallback((email: string) => startMagicLink(email), []);

  const verifyMagicLinkToken = useCallback(async (tokenValue: string) => {
    const response = await verifyMagicLink(tokenValue);
    localStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
    setToken(response.access_token);
    setUser(response.user);
  }, []);

  const logout = async () => {
    if (token) {
      const subscription = await getCurrentPushSubscription().catch(() => null);
      if (subscription) {
        const endpoint = pushSubscriptionPayload(subscription).endpoint;
        await deletePushSubscription(token, endpoint).catch(() => undefined);
        await subscription.unsubscribe().catch(() => false);
      }
    }
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const value = useMemo<AuthContextType>(
    () => ({
      isLoading,
      token,
      user,
      sendMagicLink,
      verifyMagicLinkToken,
      logout,
    }),
    [isLoading, token, user, sendMagicLink, verifyMagicLinkToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
