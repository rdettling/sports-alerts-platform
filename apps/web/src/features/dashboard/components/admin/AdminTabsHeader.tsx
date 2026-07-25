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
}: AdminTabsHeaderProps) {
  return (
    <section className="card admin-simple-panel">
      <div className="admin-tabs-header">
        <div className="admin-tab-list" role="tablist" aria-label="Admin tabs">
          {ADMIN_TABS.map((item) => (
            <button
              key={item.key}
              className={`admin-tab-button ${tab === item.key ? "active" : ""}`}
              type="button"
              aria-selected={tab === item.key}
              onClick={() => onTabChange(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="admin-tab-controls">
          <label>
            Window
            <WindowSelect value={windowValue} onChange={onWindowChange} />
          </label>
          {updatedAtLabel ? <span className="muted">Updated {updatedAtLabel}</span> : null}
        </div>
      </div>
    </section>
  );
}
