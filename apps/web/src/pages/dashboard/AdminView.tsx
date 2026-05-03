import { useEffect, useMemo, useState } from "react";

import {
  getOpsAdminOverview,
  getOpsIngestHealth,
  getOpsNeonUsage,
  type OpsAdminOverviewResponse,
  type OpsAdminOverviewWindow,
  type OpsIngestHealthResponse,
  type OpsNeonUsageResponse,
} from "../../api";
import { DevToolsView } from "./DevToolsView";

type AdminTab = "espn" | "odds" | "resend" | "db" | "tools";

type ProviderKey = "espn" | "odds" | "resend";

function timeAgoLabel(isoTime: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(isoTime).getTime()) / 1000));
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m ago`;
  }
  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)}h ago`;
  }
  return `${Math.floor(seconds / 86400)}d ago`;
}

function numberLabel(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat().format(value);
}

function dateLabel(isoTime: string | null | undefined): string {
  if (!isoTime) {
    return "n/a";
  }
  const date = new Date(isoTime);
  if (Number.isNaN(date.getTime())) {
    return "n/a";
  }
  return date.toLocaleString();
}

function statusLabel(status: "healthy" | "watch" | "at_risk"): string {
  if (status === "at_risk") {
    return "At Risk";
  }
  if (status === "watch") {
    return "Watch";
  }
  return "Healthy";
}

function normalizeProviderTab(tab: AdminTab): ProviderKey | null {
  if (tab === "espn" || tab === "resend") {
    return tab;
  }
  if (tab === "odds") {
    return "odds";
  }
  return null;
}

function findProvider(
  providers: OpsAdminOverviewResponse["providers"],
  providerKey: ProviderKey,
): OpsAdminOverviewResponse["providers"][number] | null {
  return providers.find((provider) => provider.provider === providerKey) ?? null;
}

function useAdminData(token: string, windowValue: OpsAdminOverviewWindow) {
  const [overview, setOverview] = useState<OpsAdminOverviewResponse | null>(null);
  const [ingestHealth, setIngestHealth] = useState<OpsIngestHealthResponse | null>(null);
  const [neonUsage, setNeonUsage] = useState<OpsNeonUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      if (active) {
        setLoading(true);
        setError(null);
      }
      try {
        const [overviewResponse, ingestHealthResponse, neonUsageResponse] = await Promise.all([
          getOpsAdminOverview(token, windowValue, { limit: 30 }),
          getOpsIngestHealth(token, 40),
          getOpsNeonUsage(token),
        ]);
        if (active) {
          setOverview(overviewResponse);
          setIngestHealth(ingestHealthResponse);
          setNeonUsage(neonUsageResponse);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load admin data");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    load();
    const interval = globalThis.setInterval(load, 30_000);
    return () => {
      active = false;
      globalThis.clearInterval(interval);
    };
  }, [token, windowValue]);

  return { overview, ingestHealth, neonUsage, loading, error };
}

function ProviderPanel({
  provider,
}: {
  provider: OpsAdminOverviewResponse["providers"][number] | null;
}) {
  if (!provider) {
    return (
      <section className="card admin-simple-panel">
        <h3>No provider data yet</h3>
        <p className="muted">No telemetry has been recorded for this provider in the selected window.</p>
      </section>
    );
  }

  return (
    <div className="admin-simple-stack">
      <section className="card admin-simple-panel">
        <h3>{provider.provider} usage</h3>
        <div className="admin-simple-metrics">
          <div>
            <span className="muted">Status</span>
            <strong>{statusLabel(provider.status)}</strong>
          </div>
          <div>
            <span className="muted">Utilization</span>
            <strong>{provider.utilization_pct === null ? "n/a" : `${provider.utilization_pct.toFixed(1)}%`}</strong>
          </div>
          <div>
            <span className="muted">Calls in window</span>
            <strong>{numberLabel(provider.total_calls)}</strong>
          </div>
          <div>
            <span className="muted">Window limit</span>
            <strong>{numberLabel(provider.quota_limit_window)}</strong>
          </div>
          <div>
            <span className="muted">24h limit</span>
            <strong>{numberLabel(provider.quota_limit_24h)}</strong>
          </div>
          <div>
            <span className="muted">Remaining window budget</span>
            <strong>{numberLabel(provider.remaining_budget)}</strong>
          </div>
          <div>
            <span className="muted">Error %</span>
            <strong>{provider.error_pct.toFixed(2)}%</strong>
          </div>
          <div>
            <span className="muted">Rate limited (429)</span>
            <strong>{provider.rate_limited_calls}</strong>
          </div>
        </div>
        <p className="muted">Reason: {provider.reasons[0] ?? "Within configured thresholds"}</p>
      </section>
    </div>
  );
}

function DbStatsPanel({
  ingestHealth,
  neonUsage,
}: {
  ingestHealth: OpsIngestHealthResponse | null;
  neonUsage: OpsNeonUsageResponse | null;
}) {
  const events = ingestHealth?.events ?? [];
  const states = ingestHealth?.states ?? [];
  const latestEvent = events[0] ?? null;
  const failures = events.filter((event) => event.event_type === "error");

  return (
    <div className="admin-simple-stack">
      <section className="card admin-simple-panel">
        <h3>DB stats</h3>
        <p className="muted">Internal ingest telemetry + Neon compute usage for the current billing cycle.</p>
        <p className="muted">
          {neonUsage?.dashboard_url ? (
            <a href={neonUsage.dashboard_url} target="_blank" rel="noreferrer">
              Open Neon dashboard
            </a>
          ) : null}
        </p>
        <div className="admin-simple-metrics">
          <div>
            <span className="muted">Neon CPU used</span>
            <strong>{neonUsage?.cpu_used_sec === null || neonUsage?.cpu_used_sec === undefined ? "n/a" : `${(neonUsage.cpu_used_sec / 3600).toFixed(2)} CUh`}</strong>
          </div>
          <div>
            <span className="muted">Neon active time</span>
            <strong>{neonUsage?.active_time_sec === null || neonUsage?.active_time_sec === undefined ? "n/a" : `${(neonUsage.active_time_sec / 3600).toFixed(2)}h`}</strong>
          </div>
          <div>
            <span className="muted">Avg CU while active</span>
            <strong>{neonUsage?.avg_cu_while_active === null || neonUsage?.avg_cu_while_active === undefined ? "n/a" : `${neonUsage.avg_cu_while_active.toFixed(3)} CU`}</strong>
          </div>
          <div>
            <span className="muted">Cycle end</span>
            <strong>{dateLabel(neonUsage?.consumption_period_end)}</strong>
          </div>
          <div>
            <span className="muted">Scheduler mode</span>
            <strong>{ingestHealth?.scheduler_mode ?? "n/a"}</strong>
          </div>
          <div>
            <span className="muted">Next run</span>
            <strong>{ingestHealth?.next_run_at ? timeAgoLabel(ingestHealth.next_run_at) : "n/a"}</strong>
          </div>
          <div>
            <span className="muted">Last success</span>
            <strong>{ingestHealth?.last_success_at ? timeAgoLabel(ingestHealth.last_success_at) : "n/a"}</strong>
          </div>
          <div>
            <span className="muted">Recent errors</span>
            <strong>{failures.length}</strong>
          </div>
        </div>
        <p className="muted">Tracked sources: {states.length}</p>
        {!neonUsage?.available && neonUsage?.message ? <p className="muted">{neonUsage.message}</p> : null}
      </section>

      <section className="card admin-simple-panel admin-panel-scroll">
        <h3>Recent ingest events</h3>
        <div className="admin-scroll-body">
          <ul className="list">
            {events.map((event) => (
              <li key={event.id} className="admin-simple-incident">
                <strong>{event.event_type} · {event.source_key}</strong>
                <p className="muted">
                  {timeAgoLabel(event.occurred_at)} · mode {event.mode ?? "n/a"}
                </p>
                {event.message ? <p className="muted">{event.message}</p> : null}
              </li>
            ))}
            {!latestEvent ? <li className="admin-simple-incident"><strong>No events yet</strong></li> : null}
          </ul>
        </div>
      </section>
    </div>
  );
}

export function AdminView({ token }: { token: string }) {
  const [tab, setTab] = useState<AdminTab>("espn");
  const [windowValue, setWindowValue] = useState<OpsAdminOverviewWindow>("24h");
  const { overview, ingestHealth, neonUsage, loading, error } = useAdminData(token, windowValue);

  const providerTab = normalizeProviderTab(tab);
  const provider = useMemo(() => {
    if (!overview || !providerTab) {
      return null;
    }
    return findProvider(overview.providers, providerTab);
  }, [overview, providerTab]);

  return (
    <div className="admin-page admin-tabs-page">
      <section className="card admin-simple-panel">
        <div className="admin-tabs-header">
          <div className="admin-tab-list" role="tablist" aria-label="Admin tabs">
            <button className={`admin-tab-button ${tab === "espn" ? "active" : ""}`} type="button" aria-selected={tab === "espn"} onClick={() => setTab("espn")}>ESPN</button>
            <button className={`admin-tab-button ${tab === "odds" ? "active" : ""}`} type="button" aria-selected={tab === "odds"} onClick={() => setTab("odds")}>Odds API</button>
            <button className={`admin-tab-button ${tab === "resend" ? "active" : ""}`} type="button" aria-selected={tab === "resend"} onClick={() => setTab("resend")}>Resend</button>
            <button className={`admin-tab-button ${tab === "db" ? "active" : ""}`} type="button" aria-selected={tab === "db"} onClick={() => setTab("db")}>DB Stats</button>
            <button className={`admin-tab-button ${tab === "tools" ? "active" : ""}`} type="button" aria-selected={tab === "tools"} onClick={() => setTab("tools")}>Test Tools</button>
          </div>
          <div className="admin-tab-controls">
            <label>
              Window
              <select value={windowValue} onChange={(event) => setWindowValue(event.target.value as OpsAdminOverviewWindow)}>
                <option value="1h">1h</option>
                <option value="6h">6h</option>
                <option value="24h">24h</option>
                <option value="7d">7d</option>
              </select>
            </label>
            {overview ? <span className="muted">Updated {timeAgoLabel(overview.meta.last_updated_at)}</span> : null}
          </div>
        </div>
      </section>

      {loading ? <p className="muted">Loading admin data...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !error ? (
        <div className="admin-tab-content">
          {tab === "tools" ? <DevToolsView token={token} /> : null}
          {tab === "db" ? <DbStatsPanel ingestHealth={ingestHealth} neonUsage={neonUsage} /> : null}
          {providerTab && overview ? <ProviderPanel provider={provider} /> : null}
        </div>
      ) : null}
    </div>
  );
}
