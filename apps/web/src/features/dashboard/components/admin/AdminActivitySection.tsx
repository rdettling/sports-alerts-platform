import { type OpsAdminOverviewWindow, type OpsAdminSummaryResponse } from "../../../../shared/api";
import { AdminTestAlertsPanel } from "../AdminTestAlertsPanel";
import { formatAdminDateTime, formatNullableNumber } from "./admin-format";

export function AdminActivitySection({
  token,
  summary,
  windowValue,
  onWindowChange,
}: {
  token: string;
  summary: OpsAdminSummaryResponse;
  windowValue: OpsAdminOverviewWindow;
  onWindowChange: (value: OpsAdminOverviewWindow) => void;
}) {
  const sent = summary.delivery.email_alerts.sent + summary.delivery.push_alerts.sent;
  const attempted =
    summary.delivery.email_alerts.attempted + summary.delivery.push_alerts.attempted;
  const failed = summary.delivery.email_alerts.failed + summary.delivery.push_alerts.failed;
  const oddsUsage = summary.odds_api_usage;
  const oddsPercent = oddsUsage.daily_credit_cap
    ? Math.min(100, Math.max(0, (oddsUsage.credits_used / oddsUsage.daily_credit_cap) * 100))
    : 0;

  return (
    <div className="admin-activity-grid">
      <section
        className="admin-panel admin-alert-activity-panel surface"
        aria-labelledby="admin-activity-title"
      >
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
            <tr className="admin-delivery-total">
              <th scope="row">Total</th>
              <td>{formatNullableNumber(sent)}</td>
              <td>{formatNullableNumber(attempted)}</td>
              <td className={failed ? "is-danger" : undefined}>{formatNullableNumber(failed)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="admin-panel admin-odds-panel surface" aria-labelledby="admin-odds-title">
        <div className="admin-panel-header surface-header">
          <h2 id="admin-odds-title">Odds usage</h2>
        </div>
        <div className="admin-odds-budget">
          <div>
            <span>Daily budget</span>
            <strong>
              {formatNullableNumber(oddsUsage.credits_used)}
              <small> / {formatNullableNumber(oddsUsage.daily_credit_cap)}</small>
            </strong>
          </div>
          <span>{Math.round(oddsPercent)}%</span>
        </div>
        <div
          className="admin-odds-progress"
          role="progressbar"
          aria-label="Daily odds budget used"
          aria-valuemin={0}
          aria-valuemax={oddsUsage.daily_credit_cap}
          aria-valuenow={oddsUsage.credits_used}
        >
          <span style={{ width: `${oddsPercent}%` }} />
        </div>
        <dl className="admin-odds-details">
          <div>
            <dt>Provider used</dt>
            <dd>{formatNullableNumber(oddsUsage.provider_credits_used)}</dd>
          </div>
          <div>
            <dt>Provider remaining</dt>
            <dd>{formatNullableNumber(oddsUsage.provider_credits_remaining)}</dd>
          </div>
          <div>
            <dt>Last checked</dt>
            <dd>{formatAdminDateTime(oddsUsage.provider_observed_at)}</dd>
          </div>
        </dl>
      </section>
      <AdminTestAlertsPanel token={token} items={summary.competition_settings} />
    </div>
  );
}
