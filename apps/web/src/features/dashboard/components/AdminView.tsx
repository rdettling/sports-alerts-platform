import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getOpsNeonUsage, type OpsAdminOverviewWindow } from "../../../shared/api";
import { useAdminData } from "../hooks/useAdminData";
import { AdminDeliverySection } from "./admin/AdminDeliverySection";
import { AdminJobsSection } from "./admin/AdminJobsSection";
import { AdminLeagueSettingsPanel } from "./admin/AdminLeagueSettingsPanel";
import { AdminOverviewSection } from "./admin/AdminOverviewSection";
import { AdminProvidersSection } from "./admin/AdminProvidersSection";
import { AdminTabsHeader } from "./admin/AdminTabsHeader";
import { formatElapsedTime } from "./admin/admin-format";
import { type AdminTab } from "./admin/admin-tabs";
import { DevToolsView } from "./DevToolsView";

export function AdminView({ token }: { token: string }) {
  const [tab, setTab] = useState<AdminTab>("overview");
  const [windowValue, setWindowValue] = useState<OpsAdminOverviewWindow>("24h");
  const { data, isLoading, isFetching, error } = useAdminData(token, windowValue);
  const {
    data: neonUsage,
    isLoading: neonLoading,
    error: neonQueryError,
  } = useQuery({
    queryKey: ["admin-neon", token],
    queryFn: () => getOpsNeonUsage(token),
    enabled: tab === "overview",
    refetchInterval: 60_000,
  });

  const summary = data?.summary ?? null;
  const errorMessage =
    error instanceof Error ? error.message : error ? "Failed to load admin data" : null;
  const neonError =
    neonQueryError instanceof Error
      ? neonQueryError.message
      : neonQueryError
        ? "Failed to load Neon usage"
        : null;
  const updatedAtLabel = summary ? formatElapsedTime(summary.overview.last_updated_at) : null;

  function renderTabContent() {
    if (!summary) {
      return null;
    }
    switch (tab) {
      case "overview":
        return (
          <AdminOverviewSection
            summary={summary}
            neonUsage={neonUsage}
            neonLoading={neonLoading}
            neonError={neonError}
          />
        );
      case "providers":
        return <AdminProvidersSection providers={summary.providers} />;
      case "delivery":
        return <AdminDeliverySection summary={summary} />;
      case "jobs":
        return <AdminJobsSection summary={summary} />;
      case "tools":
        return (
          <div className="admin-tools-layout">
            <AdminLeagueSettingsPanel token={token} items={summary.runtime.league_settings} />
            <DevToolsView token={token} />
          </div>
        );
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
        isRefreshing={isFetching && Boolean(summary)}
        refreshFailed={Boolean(errorMessage && summary)}
      />

      <div className="admin-content-scroll">
        {isLoading && !summary ? (
          <p className="view-feedback muted" role="status">
            Loading admin data…
          </p>
        ) : null}
        {errorMessage && !summary ? (
          <p className="view-feedback error" role="alert">
            {errorMessage}
          </p>
        ) : null}
        {errorMessage && summary ? (
          <p className="admin-refresh-error" role="alert">
            {errorMessage}
          </p>
        ) : null}
        {summary ? (
          <section
            id={`admin-panel-${tab}`}
            className="admin-tab-panel"
            role="tabpanel"
            aria-labelledby={`admin-tab-${tab}`}
            tabIndex={0}
          >
            {renderTabContent()}
          </section>
        ) : null}
      </div>
    </div>
  );
}
