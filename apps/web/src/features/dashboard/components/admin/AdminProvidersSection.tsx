import { type OpsAdminSummaryResponse } from "../../../../shared/api";
import { formatNullableNumber } from "../../utils/telemetry-format";

export function AdminProvidersSection({ providers }: { providers: OpsAdminSummaryResponse["providers"] }) {
  return (
    <section className="card admin-section admin-section-compact">
      <div className="admin-section-head">
        <div>
          <h3>Providers</h3>
          <p className="muted">API usage by provider across ESPN, Odds, and Resend.</p>
        </div>
      </div>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Provider</th>
              <th>Calls</th>
              <th>Success</th>
              <th>Errors</th>
              <th>429s</th>
              <th>Calls / hour</th>
              <th>Quota window</th>
              <th>Utilization</th>
              <th>Top endpoint</th>
            </tr>
          </thead>
          <tbody>
            {providers.map((provider) => (
              <tr key={provider.provider}>
                <td>{provider.provider}</td>
                <td>{formatNullableNumber(provider.total_calls)}</td>
                <td>{formatNullableNumber(provider.success_calls)}</td>
                <td>{formatNullableNumber(provider.error_calls)}</td>
                <td>{formatNullableNumber(provider.rate_limited_calls)}</td>
                <td>{provider.calls_per_hour.toFixed(2)}</td>
                <td>{formatNullableNumber(provider.quota_limit_window)}</td>
                <td>{provider.utilization_pct === null ? "n/a" : `${provider.utilization_pct.toFixed(1)}%`}</td>
                <td>{provider.most_used_endpoint ?? "n/a"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
