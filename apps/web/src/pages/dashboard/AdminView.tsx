import { DevToolsView } from "./DevToolsView";
import { OpsView } from "./OpsView";

export function AdminView({ token }: { token: string }) {
  return (
    <>
      <OpsView token={token} />
      <DevToolsView token={token} />
    </>
  );
}
