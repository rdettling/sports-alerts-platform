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
  if (seconds <= 0) return "Scheduled time passed — reload for status";
  if (seconds < 60) return `In ${seconds}s`;
  const minutes = Math.ceil(seconds / 60);
  if (seconds < 3600) return `In ${minutes}m`;
  return `In ${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function retryCountdown(scheduledAt: string, now: number): string {
  const value = countdown(scheduledAt, now);
  return value.startsWith("In ") ? `Retry ${value.replace("In ", "in ")}` : value;
}

function formatInterval(seconds: number): string {
  return seconds % 60 === 0 ? `${seconds / 60}m` : `${seconds}s`;
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

  return (
    <section className="admin-leagues-workspace" aria-label="League schedules">
      <div className="admin-league-panel surface">
        <div className="admin-league-table-header" aria-hidden="true">
          <span>League</span>
          <span>Live sync</span>
          <span>Odds</span>
          <span>Enabled</span>
        </div>
        <div className="admin-league-list-scroll" tabIndex={0} aria-label="League list">
          {ordered.length ? (
            <ul className="admin-league-list">
              {ordered.map((item) => {
                const jobs =
                  schedule?.jobs.filter((job) => job.competition === item.competition) ?? [];
                const live = jobs.find((job) => job.job_type === "live_sync");
                const odds = jobs.find((job) => job.job_type === "odds_sync");
                const updating = mutation.variables?.competition === item.competition;
                const interval = formatInterval(item.live_sync_interval_seconds);

                let liveValue: string;
                let liveDetail = `Every ${interval}`;
                let liveDanger = false;
                if (!item.is_enabled) {
                  liveValue = jobs.length ? "Worker confirmation pending" : "Not scheduled";
                  liveDetail = `Every ${interval} when enabled`;
                } else if (!schedule) {
                  liveValue = "Schedule unavailable";
                } else if (!live) {
                  liveValue = "Awaiting worker discovery";
                } else if (live.state === "no_upcoming") {
                  liveValue = "No upcoming games";
                  liveDetail = "Rechecked after catalog";
                } else if (!live.next_run_at) {
                  liveValue = "Schedule unavailable";
                  liveDetail = "Reload for worker status";
                } else if (live.state === "retry_scheduled") {
                  liveValue = retryCountdown(live.next_run_at, now);
                  liveDetail = `Every ${interval} after recovery`;
                  liveDanger = true;
                } else {
                  liveValue = countdown(live.next_run_at, now);
                }

                let oddsValue: string;
                let oddsDetail: string;
                let oddsDanger = false;
                if (!item.is_enabled) {
                  oddsValue = "Odds disabled";
                  oddsDetail = "Enable league to schedule";
                } else if (!schedule) {
                  oddsValue = "Schedule unavailable";
                  oddsDetail = "Reload for worker status";
                } else if (!odds) {
                  oddsValue = "Awaiting worker discovery";
                  oddsDetail = "No odds job reported";
                } else if (odds.state === "awaiting_first_result") {
                  oddsValue = "Awaiting catalog";
                  oddsDetail = "Odds run follows catalog";
                } else if (odds.state === "queued") {
                  oddsValue = "Queued";
                  oddsDetail = "Waiting to run";
                } else if (odds.state === "no_upcoming") {
                  oddsValue = "No pending odds";
                  oddsDetail = "Rechecked after catalog";
                } else if (!odds.next_run_at) {
                  oddsValue = "Schedule unavailable";
                  oddsDetail = "Reload for worker status";
                } else if (odds.state === "budget_limited") {
                  oddsValue = "Budget limited";
                  oddsDetail = retryCountdown(odds.next_run_at, now);
                } else if (odds.state === "retry_scheduled") {
                  oddsValue = retryCountdown(odds.next_run_at, now);
                  oddsDetail = "Previous attempt failed";
                  oddsDanger = true;
                } else {
                  oddsValue = countdown(odds.next_run_at, now);
                  oddsDetail = "Scheduled odds sync";
                }

                return (
                  <li
                    className={`admin-league-row${item.is_enabled ? "" : " is-disabled"}`}
                    key={item.competition}
                    aria-label={item.label}
                  >
                    <div className="admin-league-name">
                      <CompetitionMark competition={item.competition} decorative />
                      <strong>{item.label}</strong>
                    </div>
                    <dl className="admin-league-metric admin-league-live">
                      <dt>Live sync</dt>
                      <dd>
                        <strong className={liveDanger ? "is-danger" : undefined}>
                          {liveValue}
                        </strong>
                        <span>{liveDetail}</span>
                      </dd>
                    </dl>
                    <dl className="admin-league-metric admin-league-odds">
                      <dt>Odds</dt>
                      <dd>
                        <strong className={oddsDanger ? "is-danger" : undefined}>
                          {oddsValue}
                        </strong>
                        <span>{oddsDetail}</span>
                      </dd>
                    </dl>
                    <button
                      className={`admin-league-switch${item.is_enabled ? " is-on" : ""}`}
                      type="button"
                      role="switch"
                      aria-checked={item.is_enabled}
                      disabled={mutation.isPending}
                      aria-label={`${item.label} league enabled`}
                      onClick={() => mutation.mutate(item)}
                    >
                      <span className="admin-league-switch-label" aria-hidden="true">
                        {updating && mutation.isPending
                          ? "Saving…"
                          : item.is_enabled
                            ? "On"
                            : "Off"}
                      </span>
                      <span className="admin-league-switch-track" aria-hidden="true">
                        <span className="admin-league-switch-thumb" />
                      </span>
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
