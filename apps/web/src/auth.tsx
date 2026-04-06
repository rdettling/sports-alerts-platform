import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { login, me, register } from "./api";

type User = { id: number; email: string; created_at: string };

type AuthContextType = {
  isLoading: boolean;
  token: string | null;
  user: User | null;
  error: string | null;
  loginWithPassword: (email: string, password: string) => Promise<void>;
  registerWithPassword: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const AUTH_TOKEN_KEY = "sports_alerts_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [token, setToken] = useState<string | null>(localStorage.getItem(AUTH_TOKEN_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const run = async () => {
      if (!token) {
        setIsLoading(false);
        return;
      }
      try {
        const profile = await me(token);
        setUser(profile);
      } catch {
        localStorage.removeItem(AUTH_TOKEN_KEY);
        setToken(null);
      } finally {
        setIsLoading(false);
      }
    };
    run();
  }, [token]);

  const loginWithPassword = async (email: string, password: string) => {
    setError(null);
    const response = await login(email, password);
    localStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
    setToken(response.access_token);
    setUser(response.user);
  };

  const registerWithPassword = async (email: string, password: string) => {
    setError(null);
    const response = await register(email, password);
    localStorage.setItem(AUTH_TOKEN_KEY, response.access_token);
    setToken(response.access_token);
    setUser(response.user);
  };

  const logout = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const value = useMemo<AuthContextType>(
    () => ({
      isLoading,
      token,
      user,
      error,
      loginWithPassword,
      registerWithPassword,
      logout,
    }),
    [isLoading, token, user, error],
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
