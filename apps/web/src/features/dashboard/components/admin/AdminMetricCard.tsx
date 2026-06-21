export function AdminMetricCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "danger";
}) {
  return (
    <article className={`admin-metric-card ${tone === "danger" ? "is-danger" : ""}`}>
      <span className="muted">{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
