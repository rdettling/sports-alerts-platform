import { useEffect, useMemo, useState } from "react";

import { getOpsAdminOverview, type OpsAdminOverviewResponse, type OpsAdminOverviewWindow } from "../../api";

type HealthState = "healthy" | "watch" | "at_risk";

function riskLabel(status: HealthState): string {
  if (status === "at_risk") {
    return "At Risk";
  }
  if (status === "watch") {
    return "Watch";
  }
  return "Healthy";
}

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

function numberLabel(value: number | null): string {
  if (value === null) {
    return "n/a";
  }
  return new Intl.NumberFormat().format(value);
}

function trendSymbol(direction: "up" | "down" | "flat"): string {
  if (direction === "up") {
    return "↑";
  }
  if (direction === "down") {
    return "↓";
  }
  return "→";
}

function severityBadgeClass(severity: "low" | "medium" | "high"): string {
  if (severity === "high") {
    return "is-danger";
  }
  if (severity === "medium") {
    return "is-warn";
  }
  return "is-ok";
}

function useAdminOverview(token: string, windowValue: OpsAdminOverviewWindow) {
  const [data, setData] = useState<OpsAdminOverviewResponse | null>(null);
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
        const response = await getOpsAdminOverview(token, windowValue, { limit: 30 });
        if (active) {
          setData(response);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load admin telemetry");
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

  return { data, loading, error };
}

function RiskBadge({ status }: { status: HealthState }) {
  return <span className={`admin-health-pill ${status}`}>{riskLabel(status)}</span>;
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
      <span>{trendSymbol(up ? "up" : down ? "down" : "flat")}</span>
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
        <span className={`admin-health-pill ${severityBadgeClass(incident.severity)}`}>{incident.severity}</span>
        <span className="muted">{incident.provider ?? "system"}</span>
        <span className="muted">{timeAgoLabel(incident.occurred_at)}</span>
      </div>
    </li>
  );
}

export function OpsView({ token }: { token: string }) {
  const [windowValue, setWindowValue] = useState<OpsAdminOverviewWindow>("24h");
  const { data, loading, error } = useAdminOverview(token, windowValue);

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
          {data ? <span className="muted">Updated {timeAgoLabel(data.meta.last_updated_at)}</span> : null}
          {data ? <RiskBadge status={data.global_health.status} /> : null}
        </div>
      </div>

      {loading ? <p className="muted">Loading admin telemetry...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !error && data ? (
        <div className="admin-monitoring-grid">
          <section className="admin-panel">
            <h3>Risk summary</h3>
            <div className="admin-kpi-grid">
              {data.risk_cards.map((card) => (
                <article key={card.key} className="admin-kpi-card">
                  <span>{card.label}</span>
                  <strong>{numberLabel(card.value)}</strong>
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
                            limit {numberLabel(provider.quota_limit_24h)}/24h
                            {provider.quota_limit_window !== null
                              ? ` (window ${numberLabel(provider.quota_limit_window)})`
                              : ""}
                          </span>
                        </div>
                      </td>
                      <td>
                        <CapacityBar utilizationPct={provider.utilization_pct} />
                      </td>
                      <td>{numberLabel(provider.remaining_budget)}</td>
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
