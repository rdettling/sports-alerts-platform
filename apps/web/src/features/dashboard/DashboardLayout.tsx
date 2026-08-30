import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router";

import { useAuth } from "../auth/auth-context";
import { SignInModal } from "../auth/SignInModal";
import { AdminView } from "./components/AdminView";
import { AlertsView } from "./components/AlertsView";
import { CompetitionVisibilityModal } from "./components/CompetitionVisibilityModal";
import { GamesView } from "./components/GamesView";
import { TeamsView } from "./components/TeamsView";

type DashboardRouteKey = "games" | "teams" | "alerts" | "admin";

type DashboardRouteMeta = {
  key: DashboardRouteKey;
  href: string;
  label: string;
  adminOnly?: boolean;
};

const DASHBOARD_ROUTES: DashboardRouteMeta[] = [
  { key: "games", href: "/", label: "Games" },
  { key: "teams", href: "/teams", label: "Teams" },
  { key: "alerts", href: "/alerts", label: "Alerts" },
  { key: "admin", href: "/admin", label: "Admin", adminOnly: true },
];

const ROUTE_ICON_BY_KEY: Record<DashboardRouteKey, React.ReactNode> = {
  games: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M7.5 9.2h9M7.5 14.8h9M12 4v16" />
    </svg>
  ),
  teams: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 6.5h14M5 12h10M5 17.5h14" />
      <path d="M16.8 9.8l2.6 2.2-2.6 2.2" />
    </svg>
  ),
  alerts: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4a5 5 0 0 0-5 5v2.8c0 .8-.3 1.6-.8 2.3L5 16h14l-1.2-1.9a4 4 0 0 1-.8-2.3V9a5 5 0 0 0-5-5Z" />
      <path d="M10 18a2 2 0 0 0 4 0" />
    </svg>
  ),
  admin: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4.5" y="4.5" width="15" height="15" rx="2.2" />
      <path d="M8 8h8M8 12h8M8 16h8" />
    </svg>
  ),
};

export function DashboardLayout() {
  const { token, user, logout } = useAuth();
  const [signInOpen, setSignInOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [leagueVisibilityOpen, setLeagueVisibilityOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);
  const accountTriggerRef = useRef<HTMLButtonElement>(null);

  const isAuthenticated = Boolean(token && user);
  const isAdmin = isAuthenticated && user?.role === "admin";
  const navRoutes = useMemo(
    () =>
      DASHBOARD_ROUTES.filter((route) => {
        if (route.key === "games" || route.key === "teams") return true;
        if (!isAuthenticated) return false;
        return route.adminOnly ? isAdmin : true;
      }),
    [isAdmin, isAuthenticated],
  );
  const closeSignIn = useCallback(() => setSignInOpen(false), []);
  const openLeagueVisibility = useCallback(() => {
    setAccountOpen(false);
    setLeagueVisibilityOpen(true);
  }, []);
  const closeLeagueVisibility = useCallback(() => setLeagueVisibilityOpen(false), []);

  useEffect(() => {
    if (!accountOpen) return;
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!accountRef.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setAccountOpen(false);
      accountTriggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [accountOpen]);

  useEffect(() => {
    if (isAuthenticated) return;
    setAccountOpen(false);
    setLeagueVisibilityOpen(false);
  }, [isAuthenticated]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-top">
          <div className="app-brand">
            <h1>Live Game Alerts</h1>
          </div>
          <nav className="app-nav" aria-label="Dashboard sections">
            {navRoutes.map((route) => (
              <NavLink
                key={route.key}
                to={route.href}
                end={route.key === "games"}
                className={({ isActive }) => `app-nav-link ${isActive ? "active" : ""}`.trim()}
              >
                <span className="app-nav-icon" aria-hidden>
                  {ROUTE_ICON_BY_KEY[route.key]}
                </span>
                <span>{route.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="app-account">
            {token && user ? (
              <div className="account-disclosure" ref={accountRef}>
                <button
                  ref={accountTriggerRef}
                  className="account-trigger"
                  type="button"
                  aria-label={`Account for ${user.email}`}
                  aria-expanded={accountOpen}
                  aria-controls="account-menu-panel"
                  onClick={() => setAccountOpen((open) => !open)}
                >
                  <span className="account-trigger-email" aria-hidden>
                    {user.email}
                  </span>
                  <span className="account-trigger-mobile" aria-hidden>
                    Account
                  </span>
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="m4 6 4 4 4-4" />
                  </svg>
                </button>
                {accountOpen ? (
                  <div
                    id="account-menu-panel"
                    className="account-menu-panel"
                    aria-label="Account options"
                  >
                    <button
                      className="account-menu-item"
                      type="button"
                      onClick={openLeagueVisibility}
                    >
                      Leagues
                    </button>
                    <button
                      className="account-menu-item"
                      type="button"
                      onClick={() => {
                        setAccountOpen(false);
                        void logout();
                      }}
                    >
                      Sign out
                    </button>
                  </div>
                ) : null}
              </div>
            ) : token ? (
              <span className="account-status">Reconnecting…</span>
            ) : (
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => setSignInOpen(true)}
              >
                Sign in
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="app-main">
        <div className="app-content">
          <Routes>
            <Route
              path="/"
              element={
                <GamesView
                  token={token}
                  onSignInRequired={() => setSignInOpen(true)}
                  onManageLeagues={openLeagueVisibility}
                />
              }
            />
            <Route
              path="teams"
              element={
                <TeamsView
                  token={token}
                  onSignInRequired={() => setSignInOpen(true)}
                  onManageLeagues={openLeagueVisibility}
                />
              }
            />
            <Route
              path="alerts"
              element={token && user ? <AlertsView token={token} /> : <Navigate to="/" replace />}
            />
            <Route
              path="admin"
              element={isAdmin && token ? <AdminView token={token} /> : <Navigate to="/" replace />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
      <SignInModal isOpen={signInOpen} onClose={closeSignIn} />
      {token && user ? (
        <CompetitionVisibilityModal
          isOpen={leagueVisibilityOpen}
          token={token}
          onClose={closeLeagueVisibility}
        />
      ) : null}
    </div>
  );
}
