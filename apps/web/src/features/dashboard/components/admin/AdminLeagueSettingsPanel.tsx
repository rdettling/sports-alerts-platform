import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type LeagueSetting, updateOpsLeagueSetting } from "../../../../shared/api";
import {
  leagueBadgeLabel,
  leagueLogoUrl,
  messageFromUnknown,
} from "../../../../shared/lib/dashboard-ui";

function formatSyncCadence(seconds: number): string {
  if (seconds % 60 === 0) return `Every ${seconds / 60}m`;
  return `Every ${seconds}s`;
}

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
      await queryClient.invalidateQueries({ queryKey: ["teams-page", token] });
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  return (
    <section className="admin-panel surface" aria-labelledby="admin-league-runtime-title">
      <div className="admin-panel-header surface-header">
        <div>
          <h2 id="admin-league-runtime-title">League Runtime</h2>
          <p>Control which leagues consume sync resources and appear in the app.</p>
        </div>
      </div>
      {error ? (
        <p className="admin-panel-message error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="admin-league-settings-list">
        {items.map((item) => {
          const busy = toggleMutation.isPending && toggleMutation.variables?.league === item.league;
          const logoUrl = leagueLogoUrl(item.league);
          return (
            <button
              key={item.league}
              className="admin-league-setting-btn"
              type="button"
              aria-label={`${item.is_enabled ? "Disable" : "Enable"} ${item.label}`}
              disabled={busy}
              onClick={() =>
                toggleMutation.mutate({ league: item.league, isEnabled: !item.is_enabled })
              }
            >
              <span className="admin-league-setting-main">
                <span className="admin-league-setting-mark" aria-hidden>
                  {logoUrl ? (
                    <img
                      src={logoUrl}
                      alt=""
                      className={`admin-league-setting-logo league-${item.league.toLowerCase()}`.trim()}
                    />
                  ) : (
                    <span className="admin-league-setting-fallback">
                      {leagueBadgeLabel(item.league)}
                    </span>
                  )}
                </span>
                <span className="admin-league-setting-copy">
                  <strong>{item.label}</strong>
                  <span>
                    {item.is_enabled ? "Enabled" : "Disabled"} ·{" "}
                    {formatSyncCadence(item.live_sync_interval_seconds)}
                  </span>
                </span>
              </span>
              <span className="admin-league-setting-action">
                {busy ? "Saving..." : item.is_enabled ? "Disable" : "Enable"}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
