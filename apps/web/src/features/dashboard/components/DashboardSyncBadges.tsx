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
  variant?: "default" | "sidebar";
}) {
  const visibleItems = items.slice(0, 3);

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
