import { type OpsAdminOverviewWindow } from "../../../../shared/api";

import { ADMIN_TABS, type AdminTabsHeaderProps } from "./admin-tabs";

function WindowSelect({
  value,
  onChange,
}: {
  value: OpsAdminOverviewWindow;
  onChange: (next: OpsAdminOverviewWindow) => void;
}) {
  return (
    <select
      aria-label="Telemetry window"
      value={value}
      onChange={(event) => onChange(event.target.value as OpsAdminOverviewWindow)}
    >
      <option value="1h">1h</option>
      <option value="6h">6h</option>
      <option value="24h">24h</option>
      <option value="7d">7d</option>
    </select>
  );
}

export function AdminTabsHeader({
  tab,
  onTabChange,
  windowValue,
  onWindowChange,
  updatedAtLabel,
  isRefreshing,
  refreshFailed,
}: AdminTabsHeaderProps) {
  const showWindow = tab === "overview" || tab === "providers" || tab === "delivery";

  const onTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % ADMIN_TABS.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + ADMIN_TABS.length) % ADMIN_TABS.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = ADMIN_TABS.length - 1;
    if (nextIndex === null) return;

    event.preventDefault();
    const nextTab = ADMIN_TABS[nextIndex];
    onTabChange(nextTab.key);
    window.requestAnimationFrame(() =>
      document.getElementById(`admin-tab-${nextTab.key}`)?.focus(),
    );
  };

  return (
    <section className="admin-toolbar" aria-label="Admin controls">
      <div className="admin-tab-list" role="tablist" aria-label="Admin tabs">
        {ADMIN_TABS.map((item, index) => (
          <button
            key={item.key}
            id={`admin-tab-${item.key}`}
            className={`admin-tab-button ${tab === item.key ? "active" : ""}`}
            type="button"
            role="tab"
            aria-controls={`admin-panel-${item.key}`}
            aria-selected={tab === item.key}
            tabIndex={tab === item.key ? 0 : -1}
            onClick={() => onTabChange(item.key)}
            onKeyDown={(event) => onTabKeyDown(event, index)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="admin-tab-controls">
        {showWindow ? (
          <label>
            Window
            <WindowSelect value={windowValue} onChange={onWindowChange} />
          </label>
        ) : null}
        <span
          className={`admin-refresh-status ${refreshFailed ? "is-error" : ""}`.trim()}
          role="status"
          aria-live="polite"
        >
          {refreshFailed
            ? "Refresh failed"
            : isRefreshing
              ? "Refreshing…"
              : updatedAtLabel
                ? `Updated ${updatedAtLabel}`
                : ""}
        </span>
      </div>
    </section>
  );
}
