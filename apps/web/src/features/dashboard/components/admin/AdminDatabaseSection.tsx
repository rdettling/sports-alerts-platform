import { type OpsNeonUsageResponse } from "../../../../shared/api";
import { AdminMetricCard } from "./AdminMetricCard";
import { formatAdminDateTime } from "./admin-format";

export function AdminDatabaseSection({ neonUsage }: { neonUsage: OpsNeonUsageResponse | undefined }) {
  return (
    <section className="card admin-section admin-section-compact">
      <div className="admin-section-head">
        <div>
          <h3>Database</h3>
          <p className="muted">Reference database usage for the current billing window.</p>
        </div>
      </div>
      {neonUsage ? (
        <div className="admin-neon-panel">
          <div className="admin-neon-grid">
            <AdminMetricCard
              label="CPU used"
              value={neonUsage.cpu_used_sec === null || neonUsage.cpu_used_sec === undefined ? "n/a" : `${(neonUsage.cpu_used_sec / 3600).toFixed(2)} CUh`}
            />
            <AdminMetricCard
              label="Active time"
              value={neonUsage.active_time_sec === null || neonUsage.active_time_sec === undefined ? "n/a" : `${(neonUsage.active_time_sec / 3600).toFixed(2)}h`}
            />
            <AdminMetricCard
              label="Avg CU"
              value={neonUsage.avg_cu_while_active === null || neonUsage.avg_cu_while_active === undefined ? "n/a" : `${neonUsage.avg_cu_while_active.toFixed(3)} CU`}
            />
          </div>
          <div className="admin-neon-footer">
            <div className="admin-neon-cycle">
              <span className="muted">Cycle end</span>
              <strong>{formatAdminDateTime(neonUsage.consumption_period_end)}</strong>
            </div>
            {neonUsage.dashboard_url ? (
              <a className="admin-link" href={neonUsage.dashboard_url} target="_blank" rel="noreferrer">
                Open Neon dashboard
              </a>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="muted">Loading Neon usage...</p>
      )}
      {neonUsage?.message ? <p className="muted">{neonUsage.message}</p> : null}
    </section>
  );
}
