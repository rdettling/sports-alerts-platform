import { type OpsIngestHealthResponse, type OpsNeonUsageResponse } from "../../../../shared/api";
import { formatRelativeTime } from "../../utils/telemetry-format";
import { compactEventLabel, dateLabel, eventTrendPoints, sparklinePath, titleCaseMode } from "./admin-view-utils";

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <article>
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

export function AdminDbStatsPanel({
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
              <Kpi label="CPU used" value={neonUsage?.cpu_used_sec === null || neonUsage?.cpu_used_sec === undefined ? "n/a" : `${(neonUsage.cpu_used_sec / 3600).toFixed(2)} CUh`} />
              <Kpi label="Active time" value={neonUsage?.active_time_sec === null || neonUsage?.active_time_sec === undefined ? "n/a" : `${(neonUsage.active_time_sec / 3600).toFixed(2)}h`} />
              <Kpi label="Avg CU" value={neonUsage?.avg_cu_while_active === null || neonUsage?.avg_cu_while_active === undefined ? "n/a" : `${neonUsage.avg_cu_while_active.toFixed(3)} CU`} />
              <Kpi label="Cycle end" value={dateLabel(neonUsage?.consumption_period_end)} />
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
              <Kpi label="Tracked sources" value={String(states.length)} />
              <Kpi label="Recent errors" value={String(failures.length)} />
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
