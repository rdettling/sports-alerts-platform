import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type LeagueSetting, updateOpsLeagueSetting } from "../../../../shared/api";
import { messageFromUnknown } from "../../../../shared/lib/dashboard-ui";

export function AdminLeagueSettingsPanel({
  token,
  items,
}: {
  token: string;
  items: LeagueSetting[];
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const toggleMutation = useMutation({
    mutationFn: ({ league, isEnabled }: { league: LeagueSetting["league"]; isEnabled: boolean }) =>
      updateOpsLeagueSetting(token, league, isEnabled),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-page", token] });
      await queryClient.invalidateQueries({ queryKey: ["games-page", token] });
      await queryClient.invalidateQueries({ queryKey: ["following-page", token] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-sync-items"] });
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  return (
    <section className="card admin-simple-panel">
      <div className="admin-db-card-head">
        <div>
          <h3>League Runtime</h3>
          <p className="muted">Enable leagues that should consume sync resources and appear in user-facing UI.</p>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="admin-action-list">
        {items.map((item) => {
          const busy = toggleMutation.isPending && toggleMutation.variables?.league === item.league;
          return (
            <button
              key={item.league}
              className="admin-test-btn"
              type="button"
              disabled={busy}
              onClick={() => toggleMutation.mutate({ league: item.league, isEnabled: !item.is_enabled })}
            >
              <span>{item.label} {item.is_enabled ? "enabled" : "disabled"}</span>
              <span className="admin-test-btn-meta">{busy ? "Saving..." : item.is_enabled ? "Disable" : "Enable"}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
