import { type OpsAdminSummaryResponse, type OpsNeonUsageResponse } from "../../../../shared/api";
import { formatAdminDateTime, formatNullableNumber } from "./admin-format";

function formatHours(seconds: number | null | undefined, unit: string): string {
  return seconds === null || seconds === undefined
    ? "n/a"
    : `${(seconds / 3600).toFixed(2)}${unit}`;
}

function formatEmailDelivery(summary: OpsAdminSummaryResponse): string {
  const attempted = summary.overview.total_emails_attempted;
  if (attempted === 0) return "n/a";
  return `${Math.round((summary.overview.emails_sent / attempted) * 100)}%`;
}

export function AdminOverviewSection({
  summary,
  neonUsage,
  neonLoading,
  neonError,
}: {
  summary: OpsAdminSummaryResponse;
  neonUsage: OpsNeonUsageResponse | undefined;
  neonLoading: boolean;
  neonError: string | null;
}) {
  const issueJobs = summary.runtime.jobs.filter(
    (job) =>
      job.last_error || job.backoff_until || job.status === "error" || job.status === "failed",
  ).length;
  const activity = [
    { label: "Provider calls", value: formatNullableNumber(summary.overview.total_provider_calls) },
    {
      label: "Provider errors",
      value: formatNullableNumber(summary.overview.provider_errors),
      danger: summary.overview.provider_errors > 0,
    },
    {
      label: "Rate limits",
      value: formatNullableNumber(summary.overview.provider_rate_limits),
      danger: summary.overview.provider_rate_limits > 0,
    },
    { label: "Alerts created", value: formatNullableNumber(summary.overview.total_alerts_created) },
    { label: "Email success", value: formatEmailDelivery(summary) },
    {
      label: "Email failures",
      value: formatNullableNumber(summary.overview.emails_failed),
      danger: summary.overview.emails_failed > 0,
    },
  ];

  return (
    <div className="admin-overview-grid">
      <section
        className="admin-panel admin-overview-activity surface"
        aria-labelledby="admin-activity-title"
      >
        <div className="admin-panel-header surface-header">
          <div>
            <h2 id="admin-activity-title">Recent Activity</h2>
            <p>Operational totals for the selected telemetry window.</p>
          </div>
        </div>
        <div className="admin-metric-grid">
          {activity.map((item) => (
            <article
              key={item.label}
              className={`admin-metric ${item.danger ? "is-danger" : ""}`.trim()}
            >
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </article>
          ))}
        </div>
      </section>

      <section className="admin-panel surface" aria-labelledby="admin-runtime-title">
        <div className="admin-panel-header surface-header">
          <div>
            <h2 id="admin-runtime-title">Runtime</h2>
            <p>Scheduler and worker activity across enabled leagues.</p>
          </div>
          <span className={`admin-status ${issueJobs > 0 ? "is-danger" : ""}`.trim()}>
            {issueJobs} {issueJobs === 1 ? "job issue" : "job issues"}
          </span>
        </div>
        <dl className="admin-detail-list">
          <div>
            <dt>Scheduler mode</dt>
            <dd>{summary.runtime.scheduler_mode.replace(/_/g, " ")}</dd>
          </div>
          <div>
            <dt>Active leagues</dt>
            <dd>{summary.runtime.active_leagues.length}</dd>
          </div>
          <div>
            <dt>Next run</dt>
            <dd>{formatAdminDateTime(summary.runtime.next_run_at)}</dd>
          </div>
          <div>
            <dt>Previous success</dt>
            <dd>{formatAdminDateTime(summary.runtime.last_success_at)}</dd>
          </div>
        </dl>
      </section>

      <section className="admin-panel surface" aria-labelledby="admin-neon-title">
        <div className="admin-panel-header surface-header">
          <div>
            <h2 id="admin-neon-title">Database</h2>
            <p>Neon usage for the current billing cycle.</p>
          </div>
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
        {!neonLoading && !neonError && neonUsage ? (
          neonUsage.available ? (
            <dl className="admin-detail-list">
              <div>
                <dt>CPU used</dt>
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
    </div>
  );
}
