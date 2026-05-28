import { type OpsAdminOverviewWindow } from "../../../../shared/api";

import { type AdminTabsHeaderProps } from "./admin-view-types";

function WindowSelect({
  value,
  onChange,
}: {
  value: OpsAdminOverviewWindow;
  onChange: (next: OpsAdminOverviewWindow) => void;
}) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value as OpsAdminOverviewWindow)}>
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
          <button className={`admin-tab-button ${tab === "espn" ? "active" : ""}`} type="button" aria-selected={tab === "espn"} onClick={() => onTabChange("espn")}>ESPN</button>
          <button className={`admin-tab-button ${tab === "odds" ? "active" : ""}`} type="button" aria-selected={tab === "odds"} onClick={() => onTabChange("odds")}>Odds API</button>
          <button className={`admin-tab-button ${tab === "resend" ? "active" : ""}`} type="button" aria-selected={tab === "resend"} onClick={() => onTabChange("resend")}>Resend</button>
          <button className={`admin-tab-button ${tab === "db" ? "active" : ""}`} type="button" aria-selected={tab === "db"} onClick={() => onTabChange("db")}>DB Stats</button>
          <button className={`admin-tab-button ${tab === "tools" ? "active" : ""}`} type="button" aria-selected={tab === "tools"} onClick={() => onTabChange("tools")}>Test Tools</button>
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
