import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { type CompetitionSetting, updateOpsCompetitionSetting } from "../../../../shared/api";
import {
  competitionBadgeLabel,
  competitionLogoUrl,
  messageFromUnknown,
} from "../../../../shared/lib/dashboard-ui";
import { dashboardQueryKeys } from "../../hooks/dashboard-query-options";

function formatSyncCadence(seconds: number): string {
  if (seconds % 60 === 0) return `Every ${seconds / 60}m`;
  return `Every ${seconds}s`;
}

export function AdminCompetitionSettingsPanel({
  token,
  items,
}: {
  token: string;
  items: CompetitionSetting[];
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const toggleMutation = useMutation({
    mutationFn: ({
      competition,
      isEnabled,
    }: {
      competition: CompetitionSetting["competition"];
      isEnabled: boolean;
    }) => updateOpsCompetitionSetting(token, competition, isEnabled),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-page", token] }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.games }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.teams }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.competitions }),
      ]);
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  return (
    <section className="admin-panel surface" aria-labelledby="admin-competition-runtime-title">
      <div className="admin-panel-header surface-header">
        <div>
          <h2 id="admin-competition-runtime-title">Competition Availability</h2>
          <p>Active competitions consume sync resources and appear throughout the app.</p>
        </div>
      </div>
      {error ? (
        <p className="admin-panel-message error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="admin-competition-settings-list">
        {items.map((item) => {
          const busy =
            toggleMutation.isPending && toggleMutation.variables?.competition === item.competition;
          const logoUrl = competitionLogoUrl(item.competition);
          return (
            <button
              key={item.competition}
              className="admin-competition-setting-btn"
              type="button"
              aria-label={`${item.is_enabled ? "Deactivate" : "Activate"} ${item.label}`}
              disabled={busy}
              onClick={() =>
                toggleMutation.mutate({
                  competition: item.competition,
                  isEnabled: !item.is_enabled,
                })
              }
            >
              <span className="admin-competition-setting-main">
                <span className="admin-competition-setting-mark" aria-hidden>
                  {logoUrl ? (
                    <img
                      src={logoUrl}
                      alt=""
                      className={`admin-competition-setting-logo competition-${item.competition.toLowerCase()}`.trim()}
                    />
                  ) : (
                    <span className="admin-competition-setting-fallback">
                      {competitionBadgeLabel(item.competition)}
                    </span>
                  )}
                </span>
                <span className="admin-competition-setting-copy">
                  <strong>{item.label}</strong>
                  <span>
                    {item.is_enabled ? "Active" : "Inactive"} ·{" "}
                    {formatSyncCadence(item.live_sync_interval_seconds)}
                  </span>
                </span>
              </span>
              <span className="admin-competition-setting-action">
                {busy ? "Saving..." : item.is_enabled ? "Deactivate" : "Activate"}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
