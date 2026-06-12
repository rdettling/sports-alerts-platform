import { type HeaderSyncItem } from "../hooks/useDashboardSyncItems";

function compactAgeLabel(value: string): string {
  return value.replace(" ago", "");
}

export function DashboardSyncBadges({
  items,
  className = "",
  variant = "default",
}: {
  items: HeaderSyncItem[];
  className?: string;
  variant?: "default" | "sidebar" | "topbar";
}) {
  const visibleItems = items;

  if (variant === "topbar") {
    return (
      <div className={`sync-strip ${className}`.trim()} aria-label="Data sync status">
        <span className="sync-strip-title">Last sync</span>
        <div className="sync-strip-items">
          {visibleItems.map((item) => (
            <span key={item.key} className="sync-strip-item" title={`${item.label}: ${item.value}`}>
              <strong>{item.label}</strong>
              <span>{compactAgeLabel(item.value)}</span>
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`sync-table ${className}`.trim()} aria-label="Data sync status">
      <table className="sync-table-grid">
        <tbody>
          <tr>
            <th className="sync-table-title" colSpan={visibleItems.length}>
              Last sync
            </th>
          </tr>
          <tr>
            {visibleItems.map((item) => (
              <th key={`${item.key}-label`} scope="col" title={`${item.label}: ${item.value}`}>
                {item.label}
              </th>
            ))}
          </tr>
          <tr>
            {visibleItems.map((item) => (
              <td key={`${item.key}-value`} title={`${item.label}: ${item.value}`}>
                {variant === "sidebar" ? compactAgeLabel(item.value) : item.value}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
