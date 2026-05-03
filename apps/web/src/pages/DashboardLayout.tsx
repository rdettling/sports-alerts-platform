import { useMemo, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { useAuth } from "../auth";
import { AdminView, AlertsView, FollowingView, GamesView } from "./DashboardViews";
import { DASHBOARD_ROUTES, DashboardRouteMeta, DashboardShellProvider } from "./dashboard/shell";

const NAV_ICONS: Record<string, string> = {
  games: "◉",
  following: "◎",
  alerts: "◌",
  admin: "▦",
};

function routeForPath(pathname: string): DashboardRouteMeta {
  const segment = pathname.split("/").filter(Boolean)[0] ?? "games";
  return DASHBOARD_ROUTES.find((route) => route.path === segment) ?? DASHBOARD_ROUTES[0];
}

function relativeTimeLabel(timestamp: Date | null): string {
  if (!timestamp) return "Sync pending";
  const diff = Math.max(0, Math.floor((Date.now() - timestamp.getTime()) / 1000));
  if (diff < 60) return `Last sync ${diff}s ago`;
  const minutes = Math.floor(diff / 60);
  if (minutes < 60) return `Last sync ${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `Last sync ${hours}h ago`;
}

export function DashboardLayout() {
  const { token, user, logout } = useAuth();
  const location = useLocation();
  const [lastSync, setLastSync] = useState<Date | null>(null);

  if (!user || !token) {
    return <Navigate to="/auth" replace />;
  }

  const isAdmin = user.role === "admin";
  const currentRoute = routeForPath(location.pathname);
  const navRoutes = useMemo(
    () => DASHBOARD_ROUTES.filter((route) => (route.adminOnly ? isAdmin : true)),
    [isAdmin],
  );

  return (
    <DashboardShellProvider value={{ setLastSync }}>
      <div className="app-shell">
        <aside className="app-sidebar">
          <div className="sidebar-brand">
            <p className="sidebar-eyebrow">Platform</p>
            <h1>Sports Alerts</h1>
          </div>
          <nav className="sidebar-nav">
            {navRoutes.map((route) => (
              <NavLink
                key={route.key}
                to={route.path}
                className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`.trim()}
              >
                <span className="sidebar-icon" aria-hidden>
                  {NAV_ICONS[route.key]}
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
              <span className="status-pill">{relativeTimeLabel(lastSync)}</span>
              <span className="user-email">{user.email}</span>
              <button className="btn btn-secondary" onClick={logout}>
                Logout
              </button>
            </div>
          </header>

          <main className={`app-content ${currentRoute.key === "admin" ? "admin-context" : ""}`.trim()}>
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
    </DashboardShellProvider>
  );
}
