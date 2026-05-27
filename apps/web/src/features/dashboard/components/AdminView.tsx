import { useMemo, useState } from "react";

import {
  type OpsAdminOverviewResponse,
  type OpsAdminOverviewWindow,
  type OpsIngestHealthResponse,
  type OpsNeonUsageResponse,
} from "../../../shared/api";
import { useAdminData } from "../hooks/useAdminData";
import { formatHealthStatus, formatNullableNumber, formatRelativeTime } from "../utils/telemetry-format";
import { DevToolsView } from "./DevToolsView";

type AdminTab = "espn" | "odds" | "resend" | "db" | "tools";

type ProviderKey = "espn" | "odds" | "resend";

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

function titleCaseMode(mode: string | null | undefined): string {
  if (!mode) {
    return "n/a";
  }
  return mode.replace(/_/g, " ");
}

function compactEventLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function eventTrendPoints(events: OpsIngestHealthResponse["events"]): number[] {
  const now = Date.now();
  const bucketHours = 6;
  const buckets = Array.from({ length: bucketHours }, () => 0);
  for (const event of events) {
    const diffHours = (now - new Date(event.occurred_at).getTime()) / (1000 * 60 * 60);
    if (diffHours < 0 || diffHours >= bucketHours) {
      continue;
    }
    const idx = bucketHours - 1 - Math.floor(diffHours);
    buckets[idx] += 1;
  }
  return buckets;
}

function sparklinePath(points: number[], width: number, height: number): string {
  if (points.length === 0) {
    return "";
  }
  const max = Math.max(...points, 1);
  const stepX = points.length > 1 ? width / (points.length - 1) : width;
  return points
    .map((value, idx) => {
      const x = idx * stepX;
      const y = height - (value / max) * height;
      return `${idx === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
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
            <strong>{formatHealthStatus(provider.status)}</strong>
          </div>
          <div>
            <span className="muted">Utilization</span>
            <strong>{provider.utilization_pct === null ? "n/a" : `${provider.utilization_pct.toFixed(1)}%`}</strong>
          </div>
          <div>
            <span className="muted">Calls in window</span>
            <strong>{formatNullableNumber(provider.total_calls)}</strong>
          </div>
          <div>
            <span className="muted">Window limit</span>
            <strong>{formatNullableNumber(provider.quota_limit_window)}</strong>
          </div>
          <div>
            <span className="muted">24h limit</span>
            <strong>{formatNullableNumber(provider.quota_limit_24h)}</strong>
          </div>
          <div>
            <span className="muted">Remaining window budget</span>
            <strong>{formatNullableNumber(provider.remaining_budget)}</strong>
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
  const failures = events.filter((event) => event.event_type === "error");
  const trendPoints = eventTrendPoints(events);
  const trendPath = sparklinePath(trendPoints, 110, 28);

  return (
    <div className="admin-db-layout">
      <section className="card admin-simple-panel admin-db-shell">
        <header className="admin-db-header">
          <div>
            <h3>DB stats</h3>
            <p className="muted">Single-view database health, compute, and ingest diagnostics.</p>
          </div>
        </header>

        <div className="admin-db-grid">
          <section className="admin-db-card">
            <div className="admin-db-card-head">
              <div>
                <h4>Neon Compute</h4>
                <p className="muted">Neon compute usage for the current billing cycle.</p>
              </div>
            </div>
            <div className="admin-db-kpis">
              <article>
                <span className="muted">CPU used</span>
                <strong>{neonUsage?.cpu_used_sec === null || neonUsage?.cpu_used_sec === undefined ? "n/a" : `${(neonUsage.cpu_used_sec / 3600).toFixed(2)} CUh`}</strong>
              </article>
              <article>
                <span className="muted">Active time</span>
                <strong>{neonUsage?.active_time_sec === null || neonUsage?.active_time_sec === undefined ? "n/a" : `${(neonUsage.active_time_sec / 3600).toFixed(2)}h`}</strong>
              </article>
              <article>
                <span className="muted">Avg CU</span>
                <strong>{neonUsage?.avg_cu_while_active === null || neonUsage?.avg_cu_while_active === undefined ? "n/a" : `${neonUsage.avg_cu_while_active.toFixed(3)} CU`}</strong>
              </article>
              <article>
                <span className="muted">Cycle end</span>
                <strong>{dateLabel(neonUsage?.consumption_period_end)}</strong>
              </article>
            </div>
          </section>

          <section className="admin-db-card">
            <div className="admin-db-card-head">
              <div>
                <h4>Scheduler</h4>
                <p className="muted">Ingest scheduler status and cadence.</p>
              </div>
            </div>
            <div className="admin-db-scheduler-list">
              <article>
                <span className="muted">Mode</span>
                <strong className={`admin-health-pill ${ingestHealth?.scheduler_mode ?? "off"}`}>{titleCaseMode(ingestHealth?.scheduler_mode ?? "n/a")}</strong>
              </article>
              <article>
                <span className="muted">Next run</span>
                <strong>{ingestHealth?.next_run_at ? formatRelativeTime(ingestHealth.next_run_at) : "n/a"}</strong>
              </article>
              <article>
                <span className="muted">Last success</span>
                <strong>{ingestHealth?.last_success_at ? formatRelativeTime(ingestHealth.last_success_at) : "n/a"}</strong>
              </article>
            </div>
          </section>

          <section className="admin-db-card">
            <div className="admin-db-card-head">
              <div>
                <h4>Actions</h4>
                <p className="muted">Quick actions and links.</p>
              </div>
            </div>
            <div className="admin-db-actions">
              <a className="admin-test-btn admin-test-btn-primary" href={neonUsage?.dashboard_url ?? "#"} target="_blank" rel="noreferrer">
                <span>Open Neon Dashboard</span>
                <span className="admin-test-btn-meta">External</span>
              </a>
              <button className="admin-test-btn" type="button" disabled>
                <span>Run Snapshot</span>
                <span className="admin-test-btn-meta">Soon</span>
              </button>
            </div>
            {!neonUsage?.available && neonUsage?.message ? <p className="muted">{neonUsage.message}</p> : null}
          </section>

          <section className="admin-db-card admin-db-events-card">
            <div className="admin-db-card-head">
              <div>
                <h4>Recent Ingest Events</h4>
                <p className="muted">Sparse event log for ingest state changes and errors.</p>
              </div>
            </div>
            <div className="admin-db-events-scroll">
              <div className="admin-db-events-header">
                <span>Event</span>
                <span>Time</span>
                <span>Mode</span>
                <span>Message</span>
              </div>
              <ul className="list admin-db-events-list">
                {events.map((event) => (
                  <li key={event.id} className="admin-db-event-row">
                    <strong>{compactEventLabel(event.event_type)} · {event.source_key}</strong>
                    <span className="muted">{formatRelativeTime(event.occurred_at)}</span>
                    <span className={`admin-health-pill ${event.mode ?? "off"}`}>{titleCaseMode(event.mode ?? "off")}</span>
                    <span className="muted">{event.message ?? "state updated"}</span>
                  </li>
                ))}
                {events.length === 0 ? <li className="admin-db-event-row"><strong>No events yet</strong><span className="muted">-</span><span className="admin-health-pill off">off</span><span className="muted">waiting for first state change</span></li> : null}
              </ul>
            </div>
          </section>

          <section className="admin-db-card admin-db-health-card">
            <div className="admin-db-card-head">
              <div>
                <h4>Health &amp; Drift</h4>
                <p className="muted">System health snapshot.</p>
              </div>
            </div>
            <div className="admin-db-health-metrics">
              <article>
                <span className="muted">Tracked sources</span>
                <strong>{states.length}</strong>
              </article>
              <article>
                <span className="muted">Recent errors</span>
                <strong>{failures.length}</strong>
              </article>
            </div>
            <div className="admin-db-sparkline">
              <svg viewBox="0 0 110 28" role="img" aria-label="Ingest events trend">
                <path d={trendPath} />
              </svg>
              <span className="muted">Last 6h events</span>
            </div>
          </section>
        </div>
      </section>
    </div>
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
            {overview ? <span className="muted">Updated {formatRelativeTime(overview.meta.last_updated_at)}</span> : null}
          </div>
        </div>
      </section>

      {loading ? <p className="muted">Loading admin data...</p> : null}
      {errorMessage ? <p className="error">{errorMessage}</p> : null}

      {!loading && !errorMessage ? (
        <div className="admin-tab-content">
          {tab === "tools" ? <DevToolsView token={token} /> : null}
          {tab === "db" ? <DbStatsPanel ingestHealth={ingestHealth} neonUsage={neonUsage} /> : null}
          {providerTab && overview ? <ProviderPanel provider={provider} /> : null}
        </div>
      ) : null}
    </div>
  );
}
