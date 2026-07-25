import { useCallback, useMemo, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router";

import { useAuth } from "../auth/auth-context";
import { SignInModal } from "../auth/SignInModal";
import { AdminView } from "./components/AdminView";
import { AlertsView } from "./components/AlertsView";
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

function routeForPath(pathname: string): DashboardRouteMeta {
  const segment = pathname.split("/").filter(Boolean)[0] ?? "games";
  return DASHBOARD_ROUTES.find((route) => route.key === segment) ?? DASHBOARD_ROUTES[0];
}

export function DashboardLayout() {
  const { token, user, logout } = useAuth();
  const location = useLocation();
  const [signInOpen, setSignInOpen] = useState(false);

  const isAuthenticated = Boolean(token && user);
  const isAdmin = isAuthenticated && user?.role === "admin";
  const currentRoute = routeForPath(location.pathname);
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
              <>
                <span className="user-email">{user.email}</span>
                <button className="btn btn-secondary" onClick={logout}>
                  Logout
                </button>
              </>
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

      <main
        className={`app-main ${currentRoute.key === "admin" ? "admin-context" : ""} ${currentRoute.key === "games" ? "games-context" : ""}`.trim()}
      >
        <div className="app-content">
          <Routes>
            <Route
              path="/"
              element={<GamesView token={token} onSignInRequired={() => setSignInOpen(true)} />}
            />
            <Route path="games" element={<Navigate to="/" replace />} />
            <Route
              path="teams"
              element={<TeamsView token={token} onSignInRequired={() => setSignInOpen(true)} />}
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
    </div>
  );
}
