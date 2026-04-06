import { Link, Navigate, Route, Routes } from "react-router-dom";

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
        <Link to="">Overview</Link>
        <Link to="teams">Followed Teams</Link>
        <Link to="games">Followed Games</Link>
        <Link to="preferences">Alert Preferences</Link>
        <Link to="history">Alert History</Link>
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
