import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getOpsNeonUsage, type OpsAdminOverviewWindow } from "../../../shared/api";
import { useAdminData } from "../hooks/useAdminData";
import { formatRelativeTime } from "../utils/telemetry-format";
import { AdminDatabaseSection } from "./admin/AdminDatabaseSection";
import { AdminDeliverySection } from "./admin/AdminDeliverySection";
import { AdminJobsSection } from "./admin/AdminJobsSection";
import { AdminProvidersSection } from "./admin/AdminProvidersSection";
import { AdminTabsHeader } from "./admin/AdminTabsHeader";
import { AdminToolsSection } from "./admin/AdminToolsSection";
import { type AdminTab } from "./admin/admin-tabs";

export function AdminView({ token }: { token: string }) {
  const [tab, setTab] = useState<AdminTab>("database");
  const [windowValue, setWindowValue] = useState<OpsAdminOverviewWindow>("24h");
  const { data, isLoading, isFetching, error } = useAdminData(token, windowValue);
  const { data: neonUsage } = useQuery({
    queryKey: ["admin-neon", token],
    queryFn: () => getOpsNeonUsage(token),
    enabled: tab === "database",
    refetchInterval: 60_000,
  });

  const summary = data?.summary ?? null;
  const loading = isLoading || isFetching;
  const errorMessage =
    error instanceof Error ? error.message : error ? "Failed to load admin data" : null;
  const updatedAtLabel = summary ? formatRelativeTime(summary.overview.last_updated_at) : null;

  function renderTabContent() {
    if (!summary) {
      return null;
    }
    switch (tab) {
      case "database":
        return <AdminDatabaseSection neonUsage={neonUsage} />;
      case "providers":
        return <AdminProvidersSection providers={summary.providers} />;
      case "delivery":
        return <AdminDeliverySection summary={summary} />;
      case "jobs":
        return <AdminJobsSection summary={summary} />;
      case "tools":
        return <AdminToolsSection token={token} leagueSettings={summary.runtime.league_settings} />;
    }
  }

  return (
    <div className="admin-page">
      <AdminTabsHeader
        tab={tab}
        onTabChange={setTab}
        windowValue={windowValue}
        onWindowChange={setWindowValue}
        updatedAtLabel={updatedAtLabel}
      />

      {loading ? <p className="muted">Loading admin data...</p> : null}
      {errorMessage ? <p className="error">{errorMessage}</p> : null}

      {!loading && !errorMessage && summary ? (
        <div className="admin-content">{renderTabContent()}</div>
      ) : null}
    </div>
  );
}
