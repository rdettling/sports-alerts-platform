import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  getOpsAdminSummary,
  getOpsNeonUsage,
  type OpsAdminOverviewWindow,
} from "../../../shared/api";
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
    isFetching,
    error,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["admin-page", token, windowValue],
    queryFn: () => getOpsAdminSummary(token, windowValue),
    placeholderData: (previousData) => previousData,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  const {
    data: neonUsage,
    isLoading: neonLoading,
    error: neonQueryError,
    isFetching: neonFetching,
    refetch: refetchNeon,
  } = useQuery({
    queryKey: ["admin-neon", token],
    queryFn: () => getOpsNeonUsage(token),
    enabled: tab === "activity-tools",
    staleTime: Infinity,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const errorMessage =
    error instanceof Error ? error.message : error ? "Failed to load admin data" : null;
  const neonError =
    neonQueryError instanceof Error
      ? neonQueryError.message
      : neonQueryError
        ? "Failed to load Neon usage"
        : null;
  const isRefreshing = isFetching || (tab === "activity-tools" && neonFetching);

  function refresh() {
    void refetchSummary({ cancelRefetch: false });
    if (tab === "activity-tools") void refetchNeon({ cancelRefetch: false });
  }

  return (
    <div className={`admin-page${tab === "leagues" ? " admin-page-leagues" : ""}`}>
      <AdminTabsHeader
        tab={tab}
        onTabChange={setTab}
        isRefreshing={isRefreshing}
        refreshFailed={Boolean(errorMessage || (tab === "activity-tools" && neonError))}
        onRefresh={refresh}
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
                    neonUsage={neonUsage}
                    neonLoading={neonLoading}
                    neonError={neonError}
                  />
                )}
              </section>
            ))
          : null}
      </div>
    </div>
  );
}
