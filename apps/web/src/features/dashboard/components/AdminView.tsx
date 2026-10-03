import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getOpsAdminSummary, type OpsAdminOverviewWindow } from "../../../shared/api";
import { AdminLeaguesPanel } from "./admin/AdminLeaguesPanel";
import { AdminActivitySection } from "./admin/AdminActivitySection";
import { AdminTabsHeader } from "./admin/AdminTabsHeader";
import { ADMIN_TABS, type AdminTab } from "./admin/admin-tabs";

export function AdminView({ token }: { token: string }) {
  const [tab, setTab] = useState<AdminTab>("leagues");
  const [windowValue, setWindowValue] = useState<OpsAdminOverviewWindow>("24h");
  const {
    data: summary,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["admin-page", token, windowValue],
    queryFn: () => getOpsAdminSummary(token, windowValue),
    placeholderData: (previousData) => previousData,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  const errorMessage =
    error instanceof Error ? error.message : error ? "Failed to load admin data" : null;
  return (
    <div className={`admin-page${tab === "leagues" ? " admin-page-leagues" : ""}`}>
      <AdminTabsHeader
        tab={tab}
        onTabChange={setTab}
        neonDashboardUrl={summary?.neon_dashboard_url}
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
          <p className="admin-data-error" role="alert">
            {errorMessage}
          </p>
        ) : null}
        {summary
          ? ADMIN_TABS.map((item) => (
              <section
                key={item.key}
                id={`admin-panel-${item.key}`}
                className="admin-tab-panel"
                role="tabpanel"
                aria-labelledby={`admin-tab-${item.key}`}
                hidden={tab !== item.key}
                tabIndex={0}
              >
                {item.key === "leagues" ? (
                  <AdminLeaguesPanel
                    token={token}
                    items={summary.competition_settings}
                    schedule={summary.schedule}
                    active={tab === "leagues"}
                  />
                ) : (
                  <AdminActivitySection
                    token={token}
                    summary={summary}
                    windowValue={windowValue}
                    onWindowChange={setWindowValue}
                  />
                )}
              </section>
            ))
          : null}
      </div>
    </div>
  );
}
