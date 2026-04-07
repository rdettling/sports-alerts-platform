import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "../auth";
import { GamesView, HistoryView, OverviewView, PreferencesView, TeamsView } from "./DashboardViews";

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
        <NavLink to="" end className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
          Overview
        </NavLink>
        <NavLink to="teams" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
          Followed Teams
        </NavLink>
        <NavLink to="games" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
          Followed Games
        </NavLink>
        <NavLink to="preferences" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
          Alert Preferences
        </NavLink>
        <NavLink to="history" className={({ isActive }) => `tab-link ${isActive ? "active" : ""}`}>
          Alert History
        </NavLink>
      </nav>

      <Routes>
        <Route path="/" element={<OverviewView />} />
        <Route path="/teams" element={<TeamsView token={token} />} />
        <Route path="/games" element={<GamesView token={token} />} />
        <Route path="/preferences" element={<PreferencesView token={token} />} />
        <Route path="/history" element={<HistoryView token={token} />} />
      </Routes>
    </div>
  );
}
