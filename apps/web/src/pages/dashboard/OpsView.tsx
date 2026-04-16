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

  return (
    <section className="card">
      <div className="games-header">
        <h2>Ops</h2>
        <div className="games-toolbar">
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
        <>
          <ul className="list">
            <li>
              <span>Total calls</span>
              <strong>{summary.totals.actual_calls}</strong>
            </li>
            <li>
              <span>Success</span>
              <strong>{summary.totals.success_calls}</strong>
            </li>
            <li>
              <span>Errors</span>
              <strong>{summary.totals.error_calls}</strong>
            </li>
            <li>
              <span>Rate limited</span>
              <strong>{summary.totals.rate_limited_calls}</strong>
            </li>
          </ul>

          <h3>By provider</h3>
          <ul className="list">
            {summary.by_provider.map((provider) => (
              <li key={provider.provider}>
                <span>
                  {provider.provider} (expected: {provider.expected_calls ?? "n/a"})
                </span>
                <span>
                  actual {provider.actual_calls} | err {provider.error_calls} | 429 {provider.rate_limited_calls}
                </span>
              </li>
            ))}
          </ul>

          <h3>Latest hourly points</h3>
          <ul className="list">
            {latestByProvider.map((point) => (
              <li key={`${point.bucket_start}-${point.provider}`}>
                <span>
                  {point.provider} @ {new Date(point.bucket_start).toLocaleString()}
                </span>
                <span>
                  expected {point.expected_calls ?? "n/a"} | actual {point.actual_calls}
                </span>
              </li>
            ))}
          </ul>

          <h3>Ingest runs</h3>
          <ul className="list">
            {(ingestRuns?.items ?? []).map((run) => (
              <li key={run.ingest_run_id}>
                <span>
                  #{run.ingest_run_id} {run.status} ({run.poll_mode ?? "n/a"})
                </span>
                <span>
                  ESPN {run.actual_espn_calls}/{run.expected_espn_calls} | Odds {run.actual_odds_calls}/
                  {run.expected_odds_calls}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
