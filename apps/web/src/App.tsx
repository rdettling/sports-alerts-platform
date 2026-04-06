import { Navigate, Route, Routes } from "react-router-dom";

import { AuthPage } from "./pages/AuthPage";
import { DashboardLayout } from "./pages/DashboardLayout";
import { useAuth } from "./auth";

export default function App() {
  const { isLoading, token } = useAuth();

  if (isLoading) {
    return <div className="container">Loading...</div>;
  }

  return (
    <Routes>
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/dashboard/*" element={token ? <DashboardLayout /> : <Navigate to="/auth" replace />} />
      <Route path="*" element={<Navigate to={token ? "/dashboard" : "/auth"} replace />} />
    </Routes>
  );
}
