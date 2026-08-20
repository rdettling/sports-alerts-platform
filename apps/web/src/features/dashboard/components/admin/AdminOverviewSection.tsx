import { type OpsAdminSummaryResponse, type OpsNeonUsageResponse } from "../../../../shared/api";
import { formatAdminDateTime, formatNullableNumber } from "./admin-format";

function formatHours(seconds: number | null | undefined, unit: string): string {
  return seconds === null || seconds === undefined
    ? "n/a"
    : `${(seconds / 3600).toFixed(2)}${unit}`;
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
  const email = summary.delivery.email_alerts;
  const push = summary.delivery.push_alerts;
  const activity = [
    { label: "Alerts created", value: formatNullableNumber(summary.overview.total_alerts_created) },
    { label: "Email sent / attempted", value: `${email.sent} / ${email.attempted}` },
    {
      label: "Email failures",
      value: formatNullableNumber(email.failed),
      danger: email.failed > 0,
    },
    { label: "Push sent / attempted", value: `${push.sent} / ${push.attempted}` },
    {
      label: "Push failures",
      value: formatNullableNumber(push.failed),
      danger: push.failed > 0,
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
            <p>Alert and delivery totals for the selected activity window.</p>
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
