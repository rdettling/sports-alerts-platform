import { useMemo } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "../auth/auth-context";
import { AdminView } from "./components/AdminView";
import { AlertsView } from "./components/AlertsView";
import { DashboardSyncBadges } from "./components/DashboardSyncBadges";
import { FollowingView } from "./components/FollowingView";
import { GamesView } from "./components/GamesView";
import { useDashboardSyncItems } from "./hooks/useDashboardSyncItems";

type DashboardRouteKey = "games" | "following" | "alerts" | "admin";

type DashboardRouteMeta = {
  key: DashboardRouteKey;
  path: string;
  label: string;
  subtitle: string;
  adminOnly?: boolean;
};

const DASHBOARD_ROUTES: DashboardRouteMeta[] = [
  { key: "games", path: "games", label: "Games", subtitle: "Live game slate and follow actions" },
  { key: "following", path: "following", label: "Following", subtitle: "Manage your followed teams and games" },
  { key: "alerts", path: "alerts", label: "Alerts", subtitle: "Configure rules and review delivery history" },
  { key: "admin", path: "admin", label: "Admin", subtitle: "Operational telemetry and test tools", adminOnly: true },
];

const ROUTE_ICON_BY_KEY: Record<DashboardRouteKey, React.ReactNode> = {
  games: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M7.5 9.2h9M7.5 14.8h9M12 4v16" />
    </svg>
  ),
  following: (
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
  return DASHBOARD_ROUTES.find((route) => route.path === segment) ?? DASHBOARD_ROUTES[0];
}

export function DashboardLayout() {
  const { token, user, logout } = useAuth();
  const location = useLocation();
  const headerSyncItems = useDashboardSyncItems();

  const isAdmin = user?.role === "admin";
  const currentRoute = routeForPath(location.pathname);
  const navRoutes = useMemo(
    () => DASHBOARD_ROUTES.filter((route) => (route.adminOnly ? isAdmin : true)),
    [isAdmin],
  );

  if (!user || !token) {
    return <Navigate to="/auth" replace />;
  }

  return (
    <div className="app-shell">
        <aside className="app-sidebar">
          <div className="sidebar-brand">
            <h1>Live Game Alerts</h1>
            <DashboardSyncBadges items={headerSyncItems} className="sidebar-sync" variant="sidebar" />
          </div>
          <nav className="sidebar-nav">
            {navRoutes.map((route) => (
              <NavLink
                key={route.key}
                to={route.path}
                className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`.trim()}
              >
                <span className="sidebar-icon" aria-hidden>
                  {ROUTE_ICON_BY_KEY[route.key]}
                </span>
                <span>{route.label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>

        <div className="app-main">
          <header className="topbar">
            <div>
              <h2>{currentRoute.label}</h2>
              <p>{currentRoute.subtitle}</p>
            </div>
            <div className="topbar-meta">
              <div className="topbar-account">
                <span className="user-email">{user.email}</span>
                <button className="btn btn-secondary" onClick={logout}>
                  Logout
                </button>
              </div>
            </div>
          </header>

          <main className={`app-content ${currentRoute.key === "admin" ? "admin-context" : ""} ${currentRoute.key === "games" ? "games-context" : ""}`.trim()}>
            <Routes>
              <Route path="/" element={<Navigate to="games" replace />} />
              <Route path="games" element={<GamesView token={token} />} />
              <Route path="following" element={<FollowingView token={token} />} />
              <Route path="alerts" element={<AlertsView token={token} />} />
              <Route path="admin" element={isAdmin ? <AdminView token={token} /> : <Navigate to="games" replace />} />
              <Route path="ops" element={<Navigate to="admin" replace />} />
              <Route path="test" element={<Navigate to="admin" replace />} />
            </Routes>
          </main>
        </div>
      </div>
  );
}
