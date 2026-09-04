import { type OpsAdminSummaryResponse } from "../../../../shared/api";

export const competitionSettings: OpsAdminSummaryResponse["competition_settings"] = [
  {
    competition: "WNBA",
    sport: "basketball",
    label: "WNBA",
    badge_label: "WNBA",
    alert_types: ["game_start", "close_game_late", "overtime_start", "final_result"],
    live_sync_interval_seconds: 120,
    is_enabled: true,
  },
  {
    competition: "MLB",
    sport: "baseball",
    label: "MLB",
    badge_label: "MLB",
    alert_types: ["game_start", "inning_start", "extra_innings_start", "final_result"],
    live_sync_interval_seconds: 300,
    is_enabled: true,
  },
];

export const baseSummary: OpsAdminSummaryResponse = {
  overview: {
    window: "24h",
    total_alerts_created: 3,
    last_updated_at: "2026-06-20T08:00:00Z",
  },
  delivery: {
    email_alerts: { attempted: 3, sent: 2, failed: 1 },
    push_alerts: { attempted: 0, sent: 0, failed: 0 },
  },
  schedule: null,
  competition_settings: competitionSettings,
};

export const basketballCompetition = competitionSettings[0];
export const baseballCompetition = competitionSettings[1];
