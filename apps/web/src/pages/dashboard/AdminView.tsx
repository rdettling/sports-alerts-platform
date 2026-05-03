import { useEffect, useMemo, useState } from "react";

import {
  getOpsAdminOverview,
  getOpsApiUsageIngestRuns,
  type OpsAdminOverviewResponse,
  type OpsAdminOverviewWindow,
  type OpsIngestRunsResponse,
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
  const [ingestRuns, setIngestRuns] = useState<OpsIngestRunsResponse | null>(null);
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
        const [overviewResponse, ingestRunsResponse] = await Promise.all([
          getOpsAdminOverview(token, windowValue, { limit: 30 }),
          getOpsApiUsageIngestRuns(token, 40),
        ]);
        if (active) {
          setOverview(overviewResponse);
          setIngestRuns(ingestRunsResponse);
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

  return { overview, ingestRuns, loading, error };
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

function DbStatsPanel({ ingestRuns }: { ingestRuns: OpsIngestRunsResponse | null }) {
  const runs = ingestRuns?.items ?? [];
  const latest = runs[0] ?? null;
  const failures = runs.filter((run) => run.status !== "success");
  const successCount = runs.filter((run) => run.status === "success").length;
  const successRate = runs.length > 0 ? Math.round((successCount / runs.length) * 100) : null;
  const avgDuration =
    runs.length > 0
      ? Math.round(
          runs
            .map((run) => run.cycle_duration_seconds ?? 0)
            .reduce((sum, current) => sum + current, 0) / runs.length,
        )
      : null;

  return (
    <div className="admin-simple-stack">
      <section className="card admin-simple-panel">
        <h3>DB stats (internal)</h3>
        <p className="muted">This is internal ingest telemetry, not direct Neon billing metrics yet.</p>
        <div className="admin-simple-metrics">
          <div>
            <span className="muted">Latest cycle</span>
            <strong>{latest ? timeAgoLabel(latest.started_at) : "n/a"}</strong>
          </div>
          <div>
            <span className="muted">Success rate</span>
            <strong>{successRate === null ? "n/a" : `${successRate}%`}</strong>
          </div>
          <div>
            <span className="muted">Avg cycle duration</span>
            <strong>{avgDuration === null ? "n/a" : `${avgDuration}s`}</strong>
          </div>
          <div>
            <span className="muted">Failure count</span>
            <strong>{failures.length}</strong>
          </div>
        </div>
      </section>

      <section className="card admin-simple-panel admin-panel-scroll">
        <h3>Recent ingest runs</h3>
        <div className="admin-scroll-body">
          <ul className="list">
            {runs.map((run) => (
              <li key={run.ingest_run_id} className="admin-simple-incident">
                <strong>Run #{run.ingest_run_id} · {run.status}</strong>
                <p className="muted">
                  {timeAgoLabel(run.started_at)} · mode {run.poll_mode ?? "n/a"} · duration {run.cycle_duration_seconds ?? "n/a"}s
                </p>
                <p className="muted">
                  games {run.games_updated}/{run.games_checked} · espn {run.actual_espn_calls}/{run.expected_espn_calls} · odds {run.actual_odds_calls}/{run.expected_odds_calls}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

export function AdminView({ token }: { token: string }) {
  const [tab, setTab] = useState<AdminTab>("espn");
  const [windowValue, setWindowValue] = useState<OpsAdminOverviewWindow>("24h");
  const { overview, ingestRuns, loading, error } = useAdminData(token, windowValue);

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
          {tab === "db" ? <DbStatsPanel ingestRuns={ingestRuns} /> : null}
          {providerTab && overview ? <ProviderPanel provider={provider} /> : null}
        </div>
      ) : null}
    </div>
  );
}
