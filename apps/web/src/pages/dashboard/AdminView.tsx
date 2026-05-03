import { DevToolsView } from "./DevToolsView";
import { OpsView } from "./OpsView";

export function AdminView({ token }: { token: string }) {
  return (
    <div className="admin-page view-stack">
      <section className="panel">
        <div className="section-header">
          <h3>Admin Control Center</h3>
          <p>Operational analytics and internal test tooling for the platform.</p>
        </div>
      </section>
      <div className="admin-grid">
        <OpsView token={token} />
        <DevToolsView token={token} />
      </div>
    </div>
  );
}
