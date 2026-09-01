export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: { id: number; email: string; role: "user" | "admin"; created_at: string };
};

export type MagicLinkStartResponse = { message: string };

export type UserProfile = {
  id: number;
  email: string;
  role: "user" | "admin";
  created_at: string;
};

export type Competition =
  "NBA" | "WNBA" | "NFL" | "FBS" | "MLB" | "MLS" | "LA_LIGA" | "PREMIER_LEAGUE" | "WORLD_CUP";
export type Sport = "basketball" | "football" | "baseball" | "soccer";

export type Team = {
  id: number;
  sport: Sport;
  external_team_id: string;
  name: string;
  abbreviation: string;
  competitions: Competition[];
  conference: string | null;
};

export type GameTeam = Omit<Team, "competitions">;

export type TeamStrength = {
  wins: number | null;
  losses: number | null;
  ties: number | null;
  rank: number | null;
};

export type Game = {
  id: number;
  external_game_id: string;
  competition: Competition;
  home_team_id: number;
  away_team_id: number;
  home_team: GameTeam;
  away_team: GameTeam;
  scheduled_start_time: string;
  context_label: string | null;
  home_team_strength: TeamStrength;
  away_team_strength: TeamStrength;
  broadcast_names: string[];
  status: string;
  home_score: number | null;
  away_score: number | null;
  period: number | null;
  clock: string | null;
  is_final: boolean;
  last_ingested_at: string | null;
  odds: {
    bookmaker: string | null;
    last_update: string | null;
    outcomes: Array<{
      outcome_key: string;
      outcome_label: string;
      price_american: number | null;
      team_side: "away" | "home" | null;
    }>;
  } | null;
};

export type CompetitionSetting = {
  competition: Competition;
  sport: Sport;
  label: string;
  badge_label: string;
  alert_types: AlertType[];
  live_sync_interval_seconds: number;
  is_enabled: boolean;
};

export type CompetitionVisibility = {
  hidden_competitions: Competition[];
};

export type CurrentFollows = { teams: Team[]; games: Game[] };

export type AlertSettings = {
  is_enabled: boolean;
  close_game_margin_threshold: number | null;
  close_game_time_threshold_seconds: number | null;
  inning_start_threshold: number | null;
};

export type AlertSettingsUpdate = AlertSettings;

export type AlertPreference = AlertSettings & {
  sport: Sport;
  alert_type: string;
};

export type AlertPreferenceGroup = {
  sport: Sport;
  preferences: AlertPreference[];
};

export type GameAlertPreferenceItem = AlertSettings & {
  sport: Sport;
  alert_type: string;
  uses_sport_defaults: boolean;
};

export type GameAlertPreferences = {
  game_id: number;
  competition: Competition;
  sport: Sport;
  items: GameAlertPreferenceItem[];
};

export type AlertHistoryItem = {
  id: number;
  game_id: number;
  alert_type: string;
  triggered_at: string;
  game_external_id: string;
  home_team_abbreviation: string;
  away_team_abbreviation: string;
  deliveries: Array<{
    channel: string;
    status: string;
    attempted_at: string | null;
  }>;
};

export type AlertType =
  | "game_start"
  | "close_game_late"
  | "overtime_start"
  | "inning_start"
  | "extra_innings_start"
  | "second_half_start"
  | "extra_time_start"
  | "penalty_kicks"
  | "score_changed"
  | "final_result";
export type DeliveryStatus = "pending" | "sent" | "failed";

export type NotificationSettings = {
  email_alerts_enabled: boolean;
  push_subscription_count: number;
  push_configured: boolean;
  vapid_public_key: string | null;
};

export type PushSubscriptionStatus = {
  is_subscribed: boolean;
};

export type PushSubscriptionPayload = {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
};

export type OpsAdminOverviewWindow = "1h" | "6h" | "24h" | "7d";

export type OpsAdminSummaryResponse = {
  overview: {
    window: OpsAdminOverviewWindow;
    total_alerts_created: number;
    last_updated_at: string;
  };
  delivery: {
    email_alerts: {
      attempted: number;
      sent: number;
      failed: number;
    };
    push_alerts: {
      attempted: number;
      sent: number;
      failed: number;
    };
  };
  competition_settings: CompetitionSetting[];
};

export type OpsNeonUsageResponse = {
  available: boolean;
  project_id: string | null;
  project_name: string | null;
  dashboard_url: string | null;
  consumption_period_start: string | null;
  consumption_period_end: string | null;
  cpu_used_sec: number | null;
  active_time_sec: number | null;
  compute_last_active_at: string | null;
  avg_cu_while_active: number | null;
  message: string | null;
};
