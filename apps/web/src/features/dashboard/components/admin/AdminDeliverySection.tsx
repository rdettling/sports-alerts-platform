import { type OpsAdminSummaryResponse } from "../../../../shared/api";
import { formatNullableNumber } from "./admin-format";

function formatPercent(numerator: number, denominator: number): string {
  return denominator <= 0 ? "n/a" : `${((numerator / denominator) * 100).toFixed(0)}%`;
}

export function AdminDeliverySection({ summary }: { summary: OpsAdminSummaryResponse }) {
  const email = summary.delivery.email_alerts;
  const push = summary.delivery.push_alerts;
  const magic = summary.delivery.magic_links;
  const resend = summary.delivery.resend;
  const items = [
    {
      title: "Alert Email",
      description: "User-facing game alert delivery.",
      primaryLabel: "Sent",
      primaryValue: email.sent,
      successRate: formatPercent(email.sent, email.attempted),
      attemptedLabel: "Attempted",
      attemptedValue: email.attempted,
      failureLabel: "Failed",
      failureValue: email.failed,
    },
    {
      title: "Push",
      description: "Web Push delivery across subscribed devices.",
      primaryLabel: "Sent",
      primaryValue: push.sent,
      successRate: formatPercent(push.sent, push.attempted),
      attemptedLabel: "Attempted",
      attemptedValue: push.attempted,
      failureLabel: "Failed",
      failureValue: push.failed,
    },
    {
      title: "Magic Link",
      description: "Authentication email delivery inferred from Resend.",
      primaryLabel: "Sent",
      primaryValue: magic.sent,
      successRate: formatPercent(magic.sent, magic.attempted),
      attemptedLabel: "Attempted",
      attemptedValue: magic.attempted,
      failureLabel: "Failed",
      failureValue: magic.failed,
    },
    {
      title: "Resend",
      description: "Combined provider calls for alerts and authentication.",
      primaryLabel: "Calls",
      primaryValue: resend.total_calls,
      successRate: formatPercent(resend.success_calls, resend.total_calls),
      attemptedLabel: "Success",
      attemptedValue: resend.success_calls,
      failureLabel: "Errors / 429s",
      failureValue: resend.error_calls + resend.rate_limited_calls,
    },
  ];

  return (
    <section className="admin-panel surface" aria-labelledby="admin-delivery-title">
      <div className="admin-panel-header surface-header">
        <div>
          <h2 id="admin-delivery-title">Delivery</h2>
          <p>Channel outcomes for the selected telemetry window.</p>
        </div>
      </div>
      <div className="admin-delivery-list">
        {items.map((item) => (
          <article key={item.title} className="admin-delivery-row">
            <div className="admin-delivery-main">
              <strong>{item.title}</strong>
              <span>{item.description}</span>
            </div>
            <dl className="admin-delivery-metrics">
              <div>
                <dt>{item.primaryLabel}</dt>
                <dd>{formatNullableNumber(item.primaryValue)}</dd>
              </div>
              <div>
                <dt>Success rate</dt>
                <dd>{item.successRate}</dd>
              </div>
              <div>
                <dt>{item.attemptedLabel}</dt>
                <dd>{formatNullableNumber(item.attemptedValue)}</dd>
              </div>
              <div className={item.failureValue > 0 ? "is-danger" : ""}>
                <dt>{item.failureLabel}</dt>
                <dd>{formatNullableNumber(item.failureValue)}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
