import { type OpsAdminOverviewResponse } from "../../../../shared/api";
import { formatHealthStatus, formatNullableNumber } from "../../utils/telemetry-format";

type Provider = OpsAdminOverviewResponse["providers"][number];

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function AdminProviderPanel({ provider }: { provider: Provider | null }) {
  if (!provider) {
    return (
      <section className="card admin-simple-panel">
        <h3>No provider data yet</h3>
        <p className="muted">No telemetry has been recorded for this provider in the selected window.</p>
      </section>
    );
  }

  return (
    <div className="admin-simple-stack">
      <section className="card admin-simple-panel">
        <h3>{provider.provider} usage</h3>
        <div className="admin-simple-metrics">
          <MetricTile label="Status" value={formatHealthStatus(provider.status)} />
          <MetricTile label="Utilization" value={provider.utilization_pct === null ? "n/a" : `${provider.utilization_pct.toFixed(1)}%`} />
          <MetricTile label="Calls in window" value={formatNullableNumber(provider.total_calls)} />
          <MetricTile label="Window limit" value={formatNullableNumber(provider.quota_limit_window)} />
          <MetricTile label="24h limit" value={formatNullableNumber(provider.quota_limit_24h)} />
          <MetricTile label="Remaining window budget" value={formatNullableNumber(provider.remaining_budget)} />
          <MetricTile label="Error %" value={`${provider.error_pct.toFixed(2)}%`} />
          <MetricTile label="Rate limited (429)" value={String(provider.rate_limited_calls)} />
        </div>
        <p className="muted">Reason: {provider.reasons[0] ?? "Within configured thresholds"}</p>
      </section>
    </div>
  );
}
