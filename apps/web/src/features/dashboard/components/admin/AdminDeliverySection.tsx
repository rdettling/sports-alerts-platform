import { type OpsAdminSummaryResponse } from "../../../../shared/api";
import { formatNullableNumber } from "../../utils/telemetry-format";

function formatPercent(numerator: number, denominator: number): string {
  if (denominator <= 0) {
    return "n/a";
  }
  return `${((numerator / denominator) * 100).toFixed(0)}%`;
}

function DeliveryStatCard({
  title,
  description,
  primaryLabel,
  primaryValue,
  secondaryLabel,
  secondaryValue,
  rows,
}: {
  title: string;
  description: string;
  primaryLabel: string;
  primaryValue: string;
  secondaryLabel: string;
  secondaryValue: string;
  rows: Array<{ label: string; value: string; tone?: "default" | "danger" }>;
}) {
  return (
    <article className="admin-delivery-card">
      <div className="admin-delivery-card-head">
        <div>
          <h4>{title}</h4>
          <p className="muted">{description}</p>
        </div>
      </div>
      <div className="admin-delivery-card-summary">
        <div>
          <span className="admin-tools-label">{primaryLabel}</span>
          <strong>{primaryValue}</strong>
        </div>
        <div>
          <span className="admin-tools-label">{secondaryLabel}</span>
          <strong>{secondaryValue}</strong>
        </div>
      </div>
      <div className="admin-delivery-stat-list">
        {rows.map((row) => (
          <div
            key={row.label}
            className={`admin-delivery-stat-row ${row.tone === "danger" ? "is-danger" : ""}`}
          >
            <span className="muted">{row.label}</span>
            <strong>{row.value}</strong>
          </div>
        ))}
      </div>
    </article>
  );
}

export function AdminDeliverySection({ summary }: { summary: OpsAdminSummaryResponse }) {
  const emailAlertStats = summary.delivery.email_alerts;
  const pushAlertStats = summary.delivery.push_alerts;
  const magicLinkStats = summary.delivery.magic_links;
  const resendStats = summary.delivery.resend;

  return (
    <section className="card admin-section admin-section-compact">
      <div className="admin-section-head">
        <div>
          <h3>Delivery</h3>
          <p className="muted">Alert delivery by channel, plus auth email and Resend traffic.</p>
        </div>
      </div>
      <div className="admin-delivery-grid">
        <DeliveryStatCard
          title="Alert emails"
          description="Email attempts for user-facing game alerts."
          primaryLabel="Sent"
          primaryValue={formatNullableNumber(emailAlertStats.sent)}
          secondaryLabel="Success rate"
          secondaryValue={formatPercent(emailAlertStats.sent, emailAlertStats.attempted)}
          rows={[
            { label: "Attempted", value: formatNullableNumber(emailAlertStats.attempted) },
            {
              label: "Failed",
              value: formatNullableNumber(emailAlertStats.failed),
              tone: emailAlertStats.failed > 0 ? "danger" : "default",
            },
          ]}
        />
        <DeliveryStatCard
          title="Push alerts"
          description="Web Push attempts aggregated across subscribed devices."
          primaryLabel="Sent"
          primaryValue={formatNullableNumber(pushAlertStats.sent)}
          secondaryLabel="Success rate"
          secondaryValue={formatPercent(pushAlertStats.sent, pushAlertStats.attempted)}
          rows={[
            { label: "Attempted", value: formatNullableNumber(pushAlertStats.attempted) },
            {
              label: "Failed",
              value: formatNullableNumber(pushAlertStats.failed),
              tone: pushAlertStats.failed > 0 ? "danger" : "default",
            },
          ]}
        />
        <DeliveryStatCard
          title="Magic links"
          description="Auth email attempts inferred from Resend traffic."
          primaryLabel="Sent"
          primaryValue={formatNullableNumber(magicLinkStats.sent)}
          secondaryLabel="Success rate"
          secondaryValue={formatPercent(magicLinkStats.sent, magicLinkStats.attempted)}
          rows={[
            { label: "Attempted", value: formatNullableNumber(magicLinkStats.attempted) },
            {
              label: "Failed",
              value: formatNullableNumber(magicLinkStats.failed),
              tone: magicLinkStats.failed > 0 ? "danger" : "default",
            },
          ]}
        />
        <DeliveryStatCard
          title="Resend API"
          description="Combined provider call volume for alerts and auth."
          primaryLabel="Calls"
          primaryValue={formatNullableNumber(resendStats.total_calls)}
          secondaryLabel="Success rate"
          secondaryValue={formatPercent(resendStats.success_calls, resendStats.total_calls)}
          rows={[
            { label: "Success", value: formatNullableNumber(resendStats.success_calls) },
            {
              label: "Errors",
              value: formatNullableNumber(resendStats.error_calls),
              tone: resendStats.error_calls > 0 ? "danger" : "default",
            },
            {
              label: "429s",
              value: formatNullableNumber(resendStats.rate_limited_calls),
              tone: resendStats.rate_limited_calls > 0 ? "danger" : "default",
            },
          ]}
        />
      </div>
    </section>
  );
}
