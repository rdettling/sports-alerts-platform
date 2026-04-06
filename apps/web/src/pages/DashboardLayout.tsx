import { Link, Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "../auth";

function Placeholder({ title }: { title: string }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      <p>Milestone 1 placeholder view.</p>
    </section>
  );
}

export function DashboardLayout() {
  const { user, logout } = useAuth();
  if (!user) {
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
        <Route path="/" element={<Placeholder title="Overview" />} />
        <Route path="/teams" element={<Placeholder title="Followed Teams" />} />
        <Route path="/games" element={<Placeholder title="Followed Games" />} />
        <Route path="/preferences" element={<Placeholder title="Alert Preferences" />} />
        <Route path="/history" element={<Placeholder title="Alert History" />} />
      </Routes>
    </div>
  );
}
