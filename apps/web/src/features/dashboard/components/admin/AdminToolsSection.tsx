import { type OpsAdminSummaryResponse } from "../../../../shared/api";
import { DevToolsView } from "../DevToolsView";
import { AdminLeagueSettingsPanel } from "./AdminLeagueSettingsPanel";

export function AdminToolsSection({
  token,
  leagueSettings,
}: {
  token: string;
  leagueSettings: OpsAdminSummaryResponse["runtime"]["league_settings"];
}) {
  return (
    <div className="admin-tools-layout">
      <AdminLeagueSettingsPanel token={token} items={leagueSettings} />
      <DevToolsView token={token} />
    </div>
  );
}
