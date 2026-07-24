import { Route, Routes } from "react-router-dom";

import { AuthCallbackPage } from "../features/auth/AuthCallbackPage";
import { DashboardLayout } from "../features/dashboard/DashboardLayout";
import { useAuth } from "../features/auth/auth-context";

export default function App() {
  const { isLoading } = useAuth();

  if (isLoading) {
    return <div className="container">Loading...</div>;
  }

  return (
    <Routes>
      <Route path="/auth" element={<AuthCallbackPage />} />
      <Route path="/*" element={<DashboardLayout />} />
    </Routes>
  );
}
