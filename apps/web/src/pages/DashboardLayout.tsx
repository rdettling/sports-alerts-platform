import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "../auth";
import { AlertsView, DevToolsView, FollowingView, GamesView } from "./DashboardViews";

export function DashboardLayout() {
  const { token, user, logout } = useAuth();
  const devModeValue = ((import.meta.env.DEV_MODE ?? import.meta.env.VITE_DEV_MODE ?? "") as string).toLowerCase();
  const isDevMode = devModeValue === "true" || devModeValue === "1" || devModeValue === "yes" || devModeValue === "on";
  if (!user || !token) {
    return <Navigate to="/auth" replace />;
  }

  return (
    <div className="container">
      <header className="header">
        <h1>Dashboard</h1>
        <div>
          <span>{user.email}</span>
          <button onClick={logout}>Logout</button>
        </div>
      </header>

      <nav className="tabs">
        <NavLink to="games" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
          Games
        </NavLink>
        <NavLink to="following" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
          Following
        </NavLink>
        <NavLink to="alerts" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
          Alerts
        </NavLink>
        {isDevMode ? (
          <NavLink to="test" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
            Test
          </NavLink>
        ) : null}
      </nav>

      <Routes>
        <Route path="/" element={<Navigate to="games" replace />} />
        <Route path="/games" element={<GamesView token={token} />} />
        <Route path="/following" element={<FollowingView token={token} />} />
        <Route path="/alerts" element={<AlertsView token={token} />} />
        {isDevMode ? <Route path="/test" element={<DevToolsView token={token} />} /> : null}
      </Routes>
    </div>
  );
}
