import { type OpsAdminSummaryResponse } from "../../../../shared/api";
import { formatNullableNumber } from "./admin-format";

const PROVIDER_LABELS: Record<string, string> = {
  espn: "ESPN",
  odds: "Odds",
  resend: "Resend",
};

export function AdminProvidersSection({
  providers,
}: {
  providers: OpsAdminSummaryResponse["providers"];
}) {
  return (
    <section className="admin-panel surface" aria-labelledby="admin-providers-title">
      <div className="admin-panel-header surface-header">
        <div>
          <h2 id="admin-providers-title">Providers</h2>
          <p>API activity and quota usage for the selected window.</p>
        </div>
      </div>
      {providers.length ? (
        <div className="admin-provider-list">
          {providers.map((provider) => (
            <article key={provider.provider} className="admin-provider-row">
              <div className="admin-provider-main">
                <strong>{PROVIDER_LABELS[provider.provider] ?? provider.provider}</strong>
                <span>{provider.most_used_endpoint ?? "No endpoint activity"}</span>
              </div>
              <dl className="admin-provider-metrics">
                <div>
                  <dt>Calls</dt>
                  <dd>{formatNullableNumber(provider.total_calls)}</dd>
                  <span>{provider.calls_per_hour.toFixed(2)}/hour</span>
                </div>
                <div>
                  <dt>Success</dt>
                  <dd>{formatNullableNumber(provider.success_calls)}</dd>
                </div>
                <div className={provider.error_calls > 0 ? "is-danger" : ""}>
                  <dt>Errors</dt>
                  <dd>{formatNullableNumber(provider.error_calls)}</dd>
                </div>
                <div className={provider.rate_limited_calls > 0 ? "is-danger" : ""}>
                  <dt>429s</dt>
                  <dd>{formatNullableNumber(provider.rate_limited_calls)}</dd>
                </div>
                <div>
                  <dt>Utilization</dt>
                  <dd>
                    {provider.utilization_pct === null
                      ? "n/a"
                      : `${provider.utilization_pct.toFixed(1)}%`}
                  </dd>
                  <span>
                    {provider.quota_limit_window === null
                      ? "No quota"
                      : `${formatNullableNumber(provider.quota_limit_window)} quota`}
                  </span>
                </div>
              </dl>
            </article>
          ))}
        </div>
      ) : (
        <p className="admin-panel-message muted">No provider activity in this window.</p>
      )}
    </section>
  );
}
