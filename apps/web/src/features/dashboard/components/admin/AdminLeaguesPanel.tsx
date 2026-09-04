import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type CompetitionSetting,
  type ScheduleSnapshot,
  updateOpsCompetitionSetting,
} from "../../../../shared/api";
import { CompetitionMark } from "../../../../shared/components/CompetitionMark";
import { dashboardQueryKeys } from "../../hooks/dashboard-query-options";

function countdown(scheduledAt: string, now: number): string {
  const seconds = Math.ceil((new Date(scheduledAt).getTime() - now) / 1000);
  if (seconds <= 0) return "Scheduled time passed — refresh for status";
  if (seconds < 60) return `In ${seconds}s`;
  const minutes = Math.ceil(seconds / 60);
  if (seconds < 3600) return `In ${minutes}m`;
  return `In ${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

export function AdminLeaguesPanel({
  token,
  items,
  schedule,
  active,
}: {
  token: string;
  items: CompetitionSetting[];
  schedule: ScheduleSnapshot | null;
  active: boolean;
}) {
  const [now, setNow] = useState(Date.now);
  const enabled = items.filter((item) => item.is_enabled);
  const ordered = [...enabled, ...items.filter((item) => !item.is_enabled)];
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (item: CompetitionSetting) =>
      updateOpsCompetitionSetting(token, item.competition, !item.is_enabled),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-page", token] }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.games }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.teams }),
        queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.competitions }),
      ]);
    },
  });

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    function updateVisibility() {
      clearInterval(timer);
      if (active && document.visibilityState === "visible") {
        setNow(Date.now());
        timer = setInterval(() => setNow(Date.now()), 1000);
      }
    }
    updateVisibility();
    document.addEventListener("visibilitychange", updateVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", updateVisibility);
    };
  }, [active]);

  const catalogExceptions = enabled.flatMap((item) => {
    const job = schedule?.jobs.find(
      (job) => job.competition === item.competition && job.job_type === "catalog_sync",
    );
    return job && ["retry_scheduled", "queued", "awaiting_first_result"].includes(job.state)
      ? [{ item, job }]
      : [];
  });
  const catalogCountdown = schedule ? countdown(schedule.next_catalog_at, now) : null;

  return (
    <section className="admin-leagues-workspace" aria-labelledby="admin-leagues-title">
      <div className="admin-league-panel surface">
        <div className="surface-header">
          <h2 id="admin-leagues-title">Leagues</h2>
          <div className="admin-catalog-status" aria-label="Shared catalog schedule">
            <div className="admin-catalog-summary">
              <strong>
                {!enabled.length
                  ? "No enabled leagues"
                  : catalogCountdown?.startsWith("In ")
                    ? `Catalog sync ${catalogCountdown.replace("In ", "in ")}`
                    : "Catalog sync"}
              </strong>
              {enabled.length > 0 && !schedule ? (
                <span>Schedule unavailable — waiting for a worker report.</span>
              ) : null}
              {enabled.length > 0 && catalogCountdown && !catalogCountdown.startsWith("In ") ? (
                <span>{catalogCountdown}</span>
              ) : null}
            </div>
            {catalogExceptions.length ? (
              <details className="admin-catalog-exceptions">
                <summary>Catalog status ({catalogExceptions.length})</summary>
                <ul
                  className="admin-catalog-exception-list"
                  tabIndex={0}
                  aria-label="Catalog exceptions"
                >
                  {catalogExceptions.map(({ item, job }) => (
                    <li key={item.competition}>
                      <strong>{item.label}</strong>
                      <span className={job.state === "retry_scheduled" ? "is-danger" : undefined}>
                        {job.state === "retry_scheduled"
                          ? `Catalog retry · ${countdown(job.next_run_at, now)}`
                          : job.state === "queued"
                            ? "Catalog pending"
                            : "Awaiting first catalog refresh"}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        </div>
        <div className="admin-league-list-scroll" tabIndex={0} aria-label="League list">
          {ordered.length ? (
            <ul className="admin-league-list">
              {ordered.map((item) => {
                const jobs =
                  schedule?.jobs.filter((job) => job.competition === item.competition) ?? [];
                const live = jobs.find((job) => job.job_type === "live_sync");
                const updating = mutation.variables?.competition === item.competition;
                return (
                  <li className="admin-league-row" key={item.competition} aria-label={item.label}>
                    <div className="admin-league-name">
                      <CompetitionMark competition={item.competition} decorative />
                      <div className="admin-league-identity">
                        <strong>{item.label}</strong>
                        <span
                          className={`admin-league-status${item.is_enabled ? " is-enabled" : ""}`}
                        >
                          {item.is_enabled ? "Enabled" : "Disabled"}
                        </span>
                      </div>
                    </div>
                    <dl className="admin-league-metrics">
                      <div>
                        <dt>Next live sync</dt>
                        <dd
                          className={
                            item.is_enabled && live?.state === "retry_scheduled"
                              ? "is-danger"
                              : undefined
                          }
                        >
                          {!item.is_enabled
                            ? jobs.length
                              ? "Worker confirmation pending"
                              : "Not scheduled"
                            : !schedule
                              ? "Schedule unavailable"
                              : !live
                                ? "Awaiting worker discovery"
                                : countdown(live.next_run_at, now)}
                        </dd>
                      </div>
                      <div>
                        <dt>Live sync interval</dt>
                        <dd>
                          {item.live_sync_interval_seconds % 60 === 0
                            ? `${item.live_sync_interval_seconds / 60}m`
                            : `${item.live_sync_interval_seconds}s`}
                        </dd>
                      </div>
                    </dl>
                    <button
                      className="admin-secondary-button"
                      type="button"
                      disabled={mutation.isPending}
                      aria-label={`${item.is_enabled ? "Disable" : "Enable"} ${item.label}`}
                      onClick={() => mutation.mutate(item)}
                    >
                      {updating && mutation.isPending
                        ? "Saving…"
                        : item.is_enabled
                          ? "Disable"
                          : "Enable"}
                    </button>
                    {updating && mutation.error ? (
                      <p className="admin-league-error error" role="alert">
                        {mutation.error.message}
                      </p>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="admin-panel-message">No leagues available.</p>
          )}
        </div>
      </div>
    </section>
  );
}
