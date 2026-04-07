import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "../auth";
import { AlertsView, FollowingView, GamesView } from "./DashboardViews";

export function DashboardLayout() {
  const { token, user, logout } = useAuth();
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
      </nav>

      <Routes>
        <Route path="/" element={<Navigate to="games" replace />} />
        <Route path="/games" element={<GamesView token={token} />} />
        <Route path="/following" element={<FollowingView token={token} />} />
        <Route path="/alerts" element={<AlertsView token={token} />} />
      </Routes>
    </div>
  );
}
