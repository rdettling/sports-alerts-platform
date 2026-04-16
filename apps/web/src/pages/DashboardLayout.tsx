import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "../auth";
import { AdminView, AlertsView, FollowingView, GamesView } from "./DashboardViews";

export function DashboardLayout() {
  const { token, user, logout } = useAuth();
  if (!user || !token) {
    return <Navigate to="/auth" replace />;
  }
  const isAdmin = user.role === "admin";

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
        {isAdmin ? (
          <NavLink to="admin" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
            Admin
          </NavLink>
        ) : null}
      </nav>

      <Routes>
        <Route path="/" element={<Navigate to="games" replace />} />
        <Route path="games" element={<GamesView token={token} />} />
        <Route path="following" element={<FollowingView token={token} />} />
        <Route path="alerts" element={<AlertsView token={token} />} />
        <Route path="admin" element={isAdmin ? <AdminView token={token} /> : <Navigate to="games" replace />} />
        <Route path="ops" element={<Navigate to="admin" replace />} />
        <Route path="test" element={<Navigate to="admin" replace />} />
      </Routes>
    </div>
  );
}
