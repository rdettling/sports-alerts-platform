import { useMemo, useState } from "react";

import { type OpsAdminOverviewResponse, type OpsAdminOverviewWindow } from "../../../shared/api";
import { useOpsOverviewData } from "../hooks/useOpsOverviewData";
import {
  formatElapsedTime,
  formatHealthStatus,
  formatNullableNumber,
  severityToBadgeClass,
  trendDirectionSymbol,
} from "../utils/telemetry-format";

function RiskBadge({ status }: { status: "healthy" | "watch" | "at_risk" }) {
  return <span className={`admin-health-pill ${status}`}>{formatHealthStatus(status)}</span>;
}

function CapacityBar({ utilizationPct }: { utilizationPct: number | null }) {
  const value = Math.min(100, Math.max(0, utilizationPct ?? 0));
  const label = utilizationPct === null ? "n/a" : `${utilizationPct.toFixed(1)}%`;
  return (
    <div className="admin-capacity-wrap">
      <div className="admin-capacity-track" role="presentation">
        <span className="admin-capacity-fill" style={{ width: `${value}%` }} />
      </div>
      <span className="admin-capacity-label">{label}</span>
    </div>
  );
}

function SparklineMini({ delta }: { delta: number }) {
  const up = delta > 0;
  const down = delta < 0;
  return (
    <span className={`admin-sparkline-mini ${up ? "up" : down ? "down" : "flat"}`}>
      <span>{trendDirectionSymbol(up ? "up" : down ? "down" : "flat")}</span>
      <span>{delta >= 0 ? `+${delta}` : String(delta)}</span>
    </span>
  );
}

function IncidentRow({ incident }: { incident: OpsAdminOverviewResponse["incidents"][number] }) {
  return (
    <li className="admin-incident-row">
      <div>
        <strong>{incident.title}</strong>
        <p className="muted">{incident.detail}</p>
      </div>
      <div className="admin-incident-meta">
        <span className={`admin-health-pill ${severityToBadgeClass(incident.severity)}`}>{incident.severity}</span>
        <span className="muted">{incident.provider ?? "system"}</span>
        <span className="muted">{formatElapsedTime(incident.occurred_at)}</span>
      </div>
    </li>
  );
}

export function OpsView({ token }: { token: string }) {
  const [windowValue, setWindowValue] = useState<OpsAdminOverviewWindow>("24h");
  const { data, isLoading, isFetching, error } = useOpsOverviewData(token, windowValue);
  const loading = isLoading || isFetching;
  const errorMessage = error instanceof Error ? error.message : error ? "Failed to load admin telemetry" : null;

  const providers = useMemo(() => data?.providers ?? [], [data]);

  return (
    <section className="card admin-ops-card admin-overview-card">
      <div className="admin-overview-toolbar">
        <div className="admin-toolbar-left">
          <label className="admin-toolbar-field">
            <span>Window</span>
            <select value={windowValue} onChange={(event) => setWindowValue(event.target.value as OpsAdminOverviewWindow)}>
              <option value="1h">1h</option>
              <option value="6h">6h</option>
              <option value="24h">24h</option>
              <option value="7d">7d</option>
            </select>
          </label>
        </div>

        <div className="admin-toolbar-right">
          {data ? <span className="muted">Updated {formatElapsedTime(data.meta.last_updated_at)}</span> : null}
          {data ? <RiskBadge status={data.global_health.status} /> : null}
        </div>
      </div>

      {loading ? <p className="muted">Loading admin telemetry...</p> : null}
      {errorMessage ? <p className="error">{errorMessage}</p> : null}

      {!loading && !errorMessage && data ? (
        <div className="admin-monitoring-grid">
          <section className="admin-panel">
            <h3>Risk summary</h3>
            <div className="admin-kpi-grid">
              {data.risk_cards.map((card) => (
                <article key={card.key} className="admin-kpi-card">
                  <span>{card.label}</span>
                  <strong>{formatNullableNumber(card.value)}</strong>
                </article>
              ))}
            </div>
          </section>

          <section className="admin-panel admin-panel-scroll">
            <div className="admin-panel-toolbar">
              <h3>Provider capacity</h3>
              <span className="muted">Sorted by risk</span>
            </div>
            <div className="admin-scroll-body">
              <table className="admin-provider-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Utilization</th>
                    <th>Remaining</th>
                    <th>Calls/hr</th>
                    <th>Error %</th>
                    <th>429</th>
                    <th>Trend</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {providers.map((provider) => (
                    <tr key={provider.provider}>
                      <td>
                        <div className="admin-provider-name">
                          <strong>{provider.provider}</strong>
                          <span className="muted">
                            limit {formatNullableNumber(provider.quota_limit_24h)}/24h
                            {provider.quota_limit_window !== null
                              ? ` (window ${formatNullableNumber(provider.quota_limit_window)})`
                              : ""}
                          </span>
                        </div>
                      </td>
                      <td>
                        <CapacityBar utilizationPct={provider.utilization_pct} />
                      </td>
                      <td>{formatNullableNumber(provider.remaining_budget)}</td>
                      <td>{provider.calls_per_hour.toFixed(2)}</td>
                      <td>{provider.error_pct.toFixed(1)}%</td>
                      <td>{provider.rate_limited_calls}</td>
                      <td>
                        <SparklineMini delta={provider.trend_delta_calls} />
                      </td>
                      <td>
                        <div className="admin-status-cell">
                          <RiskBadge status={provider.status} />
                          <span className="muted">{provider.reasons[0]}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="admin-panel admin-panel-scroll">
            <div className="admin-panel-toolbar">
              <h3>Recent incidents</h3>
              <span className="muted">{data.incidents.length} items</span>
            </div>
            <div className="admin-scroll-body">
              <ul className="list">
                {data.incidents.map((incident) => (
                  <IncidentRow key={incident.id} incident={incident} />
                ))}
              </ul>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
