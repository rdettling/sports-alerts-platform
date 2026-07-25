import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type LeagueSetting, updateOpsLeagueSetting } from "../../../../shared/api";
import { leagueBadgeLabel, leagueLogoUrl, messageFromUnknown } from "../../../../shared/lib/dashboard-ui";

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
    <section className="card admin-section">
      <div className="admin-section-head">
        <div>
          <h3>League Runtime</h3>
          <p className="muted">Enable leagues that should consume sync resources and appear in user-facing UI.</p>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
      <div className="admin-league-settings-list">
        {items.map((item) => {
          const busy = toggleMutation.isPending && toggleMutation.variables?.league === item.league;
          const logoUrl = leagueLogoUrl(item.league);
          return (
            <button
              key={item.league}
              className="admin-league-setting-btn"
              type="button"
              disabled={busy}
              onClick={() => toggleMutation.mutate({ league: item.league, isEnabled: !item.is_enabled })}
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
                    <span className="admin-league-setting-fallback">{leagueBadgeLabel(item.league)}</span>
                  )}
                </span>
                <span className="admin-league-setting-copy">
                  <strong>{item.label}</strong>
                  <span className="admin-test-btn-meta">{item.is_enabled ? "Enabled" : "Disabled"}</span>
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
