import { useMemo, useState } from "react";

import { type OpsAdminOverviewWindow } from "../../../shared/api";
import { useAdminData } from "../hooks/useAdminData";
import { formatRelativeTime } from "../utils/telemetry-format";
import { AdminDbStatsPanel } from "./admin/AdminDbStatsPanel";
import { AdminProviderPanel } from "./admin/AdminProviderPanel";
import { AdminTabsHeader } from "./admin/AdminTabsHeader";
import { findProvider, normalizeProviderTab } from "./admin/admin-view-utils";
import { type AdminTab } from "./admin/admin-view-types";
import { DevToolsView } from "./DevToolsView";

function AdminLoadingState({ loading, errorMessage }: { loading: boolean; errorMessage: string | null }) {
  return (
    <>
      {loading ? <p className="muted">Loading admin data...</p> : null}
      {errorMessage ? <p className="error">{errorMessage}</p> : null}
    </>
  );
}

export function AdminView({ token }: { token: string }) {
  const [tab, setTab] = useState<AdminTab>("espn");
  const [windowValue, setWindowValue] = useState<OpsAdminOverviewWindow>("24h");
  const { data, isLoading, isFetching, error } = useAdminData(token, windowValue);

  const loading = isLoading || isFetching;
  const errorMessage = error instanceof Error ? error.message : error ? "Failed to load admin data" : null;
  const overview = data?.overview ?? null;
  const ingestHealth = data?.ingestHealth ?? null;
  const neonUsage = data?.neonUsage ?? null;

  const providerTab = normalizeProviderTab(tab);
  const provider = useMemo(() => {
    if (!overview || !providerTab) {
      return null;
    }
    return findProvider(overview.providers, providerTab);
  }, [overview, providerTab]);

  return (
    <div className="admin-page admin-tabs-page">
      <AdminTabsHeader
        tab={tab}
        onTabChange={setTab}
        windowValue={windowValue}
        onWindowChange={setWindowValue}
        updatedAtLabel={overview ? formatRelativeTime(overview.meta.last_updated_at) : null}
      />

      <AdminLoadingState loading={loading} errorMessage={errorMessage} />

      {!loading && !errorMessage ? (
        <div className="admin-tab-content">
          {tab === "tools" ? <DevToolsView token={token} /> : null}
          {tab === "db" ? <AdminDbStatsPanel ingestHealth={ingestHealth} neonUsage={neonUsage} /> : null}
          {providerTab && overview ? <AdminProviderPanel provider={provider} /> : null}
        </div>
      ) : null}
    </div>
  );
}
