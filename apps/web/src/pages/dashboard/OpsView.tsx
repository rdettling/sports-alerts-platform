import { useEffect, useMemo, useState } from "react";

import {
  getOpsApiUsageIngestRuns,
  getOpsApiUsageSummary,
  getOpsApiUsageTimeseries,
  type OpsIngestRunsResponse,
  type OpsSummaryResponse,
  type OpsTimeseriesResponse,
  type OpsTimeseriesWindow,
  type OpsWindow,
} from "../../api";

type OpsRun = OpsIngestRunsResponse["items"][number];

function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat().format(value);
}

function relativeTimeLabel(isoTime: string, nowMs: number): string {
  const diffSeconds = Math.max(0, Math.floor((nowMs - new Date(isoTime).getTime()) / 1000));
  if (diffSeconds < 60) {
    return `${diffSeconds}s ago`;
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)}m ago`;
  }
  if (diffSeconds < 86400) {
    return `${Math.floor(diffSeconds / 3600)}h ago`;
  }
  return `${Math.floor(diffSeconds / 86400)}d ago`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || Number.isNaN(seconds)) {
    return "n/a";
  }
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

function cadenceLabel(pollMode: string | null): string {
  if (pollMode === "live") {
    return "Live: every 30s";
  }
  if (pollMode === "soon") {
    return "Soon: every 2m";
  }
  if (pollMode === "day") {
    return "Day: every 5m";
  }
  if (pollMode === "idle") {
    return "Idle: every 60m";
  }
  return "Cadence unavailable";
}

export function OpsView({ token }: { token: string }) {
  const [window, setWindow] = useState<OpsWindow>("24h");
  const [summary, setSummary] = useState<OpsSummaryResponse | null>(null);
  const [timeseries, setTimeseries] = useState<OpsTimeseriesResponse | null>(null);
  const [ingestRuns, setIngestRuns] = useState<OpsIngestRunsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const timeseriesWindow: OpsTimeseriesWindow = window === "30d" ? "7d" : window;
        const [summaryResponse, timeseriesResponse, ingestRunsResponse] = await Promise.all([
          getOpsApiUsageSummary(token, window),
          getOpsApiUsageTimeseries(token, timeseriesWindow),
          getOpsApiUsageIngestRuns(token, 75),
        ]);
        setSummary(summaryResponse);
        setTimeseries(timeseriesResponse);
        setIngestRuns(ingestRunsResponse);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load ops data");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token, window]);

  const latestByProvider = useMemo(() => {
    if (!timeseries) {
      return [];
    }
    return [...timeseries.points]
      .sort((left, right) => right.bucket_start.localeCompare(left.bucket_start))
      .slice(0, 10);
  }, [timeseries]);

  const ingestSummary = useMemo(() => {
    const runs = ingestRuns?.items ?? [];
    if (runs.length === 0) {
      return null;
    }

    const nowMs = Date.now();
    const in24h = runs.filter((run) => nowMs - new Date(run.started_at).getTime() <= 24 * 3600 * 1000);
    const denominator = in24h.length > 0 ? in24h.length : runs.length;
    const successes = (in24h.length > 0 ? in24h : runs).filter((run) => run.status === "success").length;
    const successRate = Math.round((successes / denominator) * 100);
    const durations = runs.map((run) => run.cycle_duration_seconds).filter((value): value is number => value !== null);
    const averageDuration = durations.length > 0 ? Math.round(durations.reduce((acc, value) => acc + value, 0) / durations.length) : null;
    const lastFailure = runs.find((run) => run.status !== "success");
    const latest = runs[0];

    return {
      latest,
      successRate,
      averageDuration,
      lastFailure,
      nowMs,
    };
  }, [ingestRuns]);

  return (
    <section className="card admin-ops-card">
      <div className="admin-ops-header">
        <h2>Admin Overview</h2>
        <div className="admin-toolbar">
          <label>
            Window
            <select value={window} onChange={(event) => setWindow(event.target.value as OpsWindow)}>
              <option value="24h">24h</option>
              <option value="7d">7d</option>
              <option value="30d">30d</option>
            </select>
          </label>
        </div>
      </div>

      {loading ? <p className="muted">Loading ops usage...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !error && summary ? (
        <div className="admin-ops-content">
          <section className="admin-panel">
            <h3>API usage</h3>
            <div className="admin-kpi-grid">
              <article className="admin-kpi-card">
                <span>Total calls</span>
                <strong>{summary.totals.actual_calls}</strong>
              </article>
              <article className="admin-kpi-card">
                <span>Success</span>
                <strong>{summary.totals.success_calls}</strong>
              </article>
              <article className="admin-kpi-card">
                <span>Errors</span>
                <strong>{summary.totals.error_calls}</strong>
              </article>
              <article className="admin-kpi-card">
                <span>Rate limited</span>
                <strong>{summary.totals.rate_limited_calls}</strong>
              </article>
            </div>
          </section>

          <div className="admin-ops-mid-grid">
            <section className="admin-panel admin-panel-scroll">
              <h3>By provider</h3>
              <div className="admin-scroll-body">
                <ul className="list">
                  {summary.by_provider.map((provider) => (
                    <li key={provider.provider} className="admin-metric-row">
                      <div className="admin-metric-main">
                        <span className="admin-metric-title">{provider.provider}</span>
                        <span className="admin-metric-subtitle">expected {formatCount(provider.expected_calls)}</span>
                      </div>
                      <div className="admin-metric-values">
                        <span className="admin-metric-pill">actual {formatCount(provider.actual_calls)}</span>
                        <span className="admin-metric-pill">errors {formatCount(provider.error_calls)}</span>
                        <span className="admin-metric-pill">rate-limited {formatCount(provider.rate_limited_calls)}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </section>

            <section className="admin-panel admin-panel-scroll">
              <h3>Latest hourly points</h3>
              <div className="admin-scroll-body">
                <ul className="list">
                  {latestByProvider.map((point) => (
                    <li key={`${point.bucket_start}-${point.provider}`} className="admin-metric-row">
                      <div className="admin-metric-main">
                        <span className="admin-metric-title">{point.provider}</span>
                        <span className="admin-metric-subtitle">{new Date(point.bucket_start).toLocaleString()}</span>
                      </div>
                      <div className="admin-metric-values">
                        <span className="admin-metric-pill">expected {formatCount(point.expected_calls)}</span>
                        <span className="admin-metric-pill">actual {formatCount(point.actual_calls)}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          </div>

          <section className="admin-panel admin-panel-scroll admin-ingest-panel">
            <h3>Recent ingest cycles</h3>
            <p className="muted admin-ingest-legend">Modes: Live 30s · Soon 2m · Day 5m · Idle 60m</p>
            {ingestSummary ? (
              <div className="admin-ingest-summary-grid">
                <article className="admin-ingest-summary-item">
                  <span>Last cycle</span>
                  <strong>{relativeTimeLabel(ingestSummary.latest.started_at, ingestSummary.nowMs)}</strong>
                </article>
                <article className="admin-ingest-summary-item">
                  <span>Success rate (24h)</span>
                  <strong>{ingestSummary.successRate}%</strong>
                </article>
                <article className="admin-ingest-summary-item">
                  <span>Avg duration</span>
                  <strong>{formatDuration(ingestSummary.averageDuration)}</strong>
                </article>
                <article className="admin-ingest-summary-item">
                  <span>Last failure</span>
                  <strong>
                    {ingestSummary.lastFailure
                      ? relativeTimeLabel(ingestSummary.lastFailure.started_at, ingestSummary.nowMs)
                      : "none"}
                  </strong>
                </article>
              </div>
            ) : null}
            <div className="admin-scroll-body">
              <ul className="list admin-ingest-list">
                {(ingestRuns?.items ?? []).map((run: OpsRun) => (
                  <li key={run.ingest_run_id}>
                    <div className="admin-ingest-main">
                      <span className="admin-ingest-time">{relativeTimeLabel(run.started_at, Date.now())}</span>
                      <span className={`admin-pill ${run.status === "success" ? "admin-pill-success" : "admin-pill-fail"}`}>
                        {run.status}
                      </span>
                      <span className="admin-pill admin-pill-neutral">{run.poll_mode ?? "n/a"}</span>
                      <span className="muted">{cadenceLabel(run.poll_mode)}</span>
                    </div>
                    <div className="admin-ingest-meta">
                      <span>ESPN calls {run.actual_espn_calls}/{run.expected_espn_calls}</span>
                      <span>Odds calls {run.actual_odds_calls}/{run.expected_odds_calls}</span>
                      <span>Games changed {run.games_updated}/{run.games_checked}</span>
                      <span>Duration {formatDuration(run.cycle_duration_seconds)}</span>
                      <span className="muted">run #{run.ingest_run_id}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
