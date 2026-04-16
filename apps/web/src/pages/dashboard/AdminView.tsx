import { DevToolsView } from "./DevToolsView";
import { OpsView } from "./OpsView";

export function AdminView({ token }: { token: string }) {
  return (
    <div className="admin-page">
      <div className="admin-grid">
        <OpsView token={token} />
        <DevToolsView token={token} />
      </div>
    </div>
  );
}
