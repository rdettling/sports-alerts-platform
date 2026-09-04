import {
  type OpsAdminOverviewWindow,
  type OpsAdminSummaryResponse,
  type OpsNeonUsageResponse,
} from "../../../../shared/api";
import { AdminTestAlertsPanel } from "../AdminTestAlertsPanel";
import { formatAdminDateTime, formatNullableNumber } from "./admin-format";

function formatHours(seconds: number | null | undefined, unit: string): string {
  return seconds === null || seconds === undefined
    ? "n/a"
    : `${(seconds / 3600).toFixed(2)}${unit}`;
}

export function AdminActivitySection({
  token,
  summary,
  windowValue,
  onWindowChange,
  neonUsage,
  neonLoading,
  neonError,
}: {
  token: string;
  summary: OpsAdminSummaryResponse;
  windowValue: OpsAdminOverviewWindow;
  onWindowChange: (value: OpsAdminOverviewWindow) => void;
  neonUsage: OpsNeonUsageResponse | undefined;
  neonLoading: boolean;
  neonError: string | null;
}) {
  return (
    <div className="admin-activity-grid">
      <section className="admin-panel surface" aria-labelledby="admin-activity-title">
        <div className="admin-panel-header surface-header">
          <h2 id="admin-activity-title">Alert activity</h2>
          <label className="admin-window-select">
            Window
            <select
              aria-label="Activity window"
              value={windowValue}
              onChange={(event) => onWindowChange(event.target.value as OpsAdminOverviewWindow)}
            >
              <option value="1h">1h</option>
              <option value="6h">6h</option>
              <option value="24h">24h</option>
              <option value="7d">7d</option>
            </select>
          </label>
        </div>
        <div className="admin-activity-total">
          <span>Alerts created</span>
          <strong>{formatNullableNumber(summary.overview.total_alerts_created)}</strong>
        </div>
        <table className="admin-delivery-table" aria-label="Alert delivery">
          <thead>
            <tr>
              <th scope="col">Channel</th>
              <th scope="col">Sent</th>
              <th scope="col">Attempted</th>
              <th scope="col">Failed</th>
            </tr>
          </thead>
          <tbody>
            {(
              [
                ["Email", summary.delivery.email_alerts],
                ["Push", summary.delivery.push_alerts],
              ] as const
            ).map(([channel, counts]) => (
              <tr key={channel}>
                <th scope="row">{channel}</th>
                <td>{counts.sent}</td>
                <td>{counts.attempted}</td>
                <td className={counts.failed ? "is-danger" : undefined}>{counts.failed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="admin-panel surface" aria-labelledby="admin-neon-title">
        <div className="admin-panel-header surface-header">
          <h2 id="admin-neon-title">Database</h2>
          {neonUsage?.dashboard_url ? (
            <a
              className="admin-link"
              href={neonUsage.dashboard_url}
              target="_blank"
              rel="noreferrer"
            >
              Open Neon
            </a>
          ) : null}
        </div>
        {neonLoading ? (
          <p className="admin-panel-message" role="status">
            Loading Neon usage…
          </p>
        ) : null}
        {neonError ? (
          <p className="admin-panel-message error" role="alert">
            {neonError}
          </p>
        ) : null}
        {neonUsage ? (
          neonUsage.available ? (
            <dl className="admin-detail-list">
              <div>
                <dt>Compute used</dt>
                <dd>{formatHours(neonUsage.cpu_used_sec, " CUh")}</dd>
              </div>
              <div>
                <dt>Active time</dt>
                <dd>{formatHours(neonUsage.active_time_sec, "h")}</dd>
              </div>
              <div>
                <dt>Average CU</dt>
                <dd>
                  {neonUsage.avg_cu_while_active === null ||
                  neonUsage.avg_cu_while_active === undefined
                    ? "n/a"
                    : `${neonUsage.avg_cu_while_active.toFixed(3)} CU`}
                </dd>
              </div>
              <div>
                <dt>Cycle end</dt>
                <dd>{formatAdminDateTime(neonUsage.consumption_period_end)}</dd>
              </div>
            </dl>
          ) : (
            <p className="admin-panel-message">
              {neonUsage.message ?? "Neon usage is unavailable."}
            </p>
          )
        ) : null}
      </section>
      <AdminTestAlertsPanel token={token} items={summary.competition_settings} />
    </div>
  );
}
