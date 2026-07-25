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

export type League = "NBA" | "WNBA" | "MLB" | "MLS" | "WORLD_CUP";
export type Sport = "basketball" | "baseball" | "soccer";

export type Team = {
  id: number;
  external_team_id: string;
  league: League;
  name: string;
  abbreviation: string;
};

export type Game = {
  id: number;
  external_game_id: string;
  league: League;
  home_team_id: number;
  away_team_id: number;
  scheduled_start_time: string;
  context_label: string | null;
  status: string;
  home_score: number | null;
  away_score: number | null;
  period: number | null;
  clock: string | null;
  is_final: boolean;
  last_ingested_at: string | null;
  odds: {
    market: string;
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

export type LeagueSetting = {
  league: League;
  sport: Sport;
  label: string;
  badge_label: string;
  alert_types: AlertType[];
  live_sync_interval_seconds: number;
  default_test_matchup: [string, string];
  is_enabled: boolean;
};

export type CurrentFollows = { teams: Team[]; games: Game[] };

export type AlertPreference = {
  league: League;
  alert_type: string;
  is_enabled: boolean;
  close_game_margin_threshold: number | null;
  close_game_time_threshold_seconds: number | null;
  inning_start_threshold: number | null;
};

export type AlertPreferenceGroup = {
  league: League;
  preferences: AlertPreference[];
};

export type GameAlertPreferenceItem = {
  league: League;
  alert_type: string;
  use_league_default: boolean;
  is_enabled: boolean;
  close_game_margin_threshold: number | null;
  close_game_time_threshold_seconds: number | null;
  inning_start_threshold: number | null;
  override: {
    is_enabled_override: boolean | null;
    close_game_margin_threshold_override: number | null;
    close_game_time_threshold_seconds_override: number | null;
    inning_start_threshold_override: number | null;
  } | null;
};

export type GameAlertPreferences = {
  game_id: number;
  league: League;
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
export type DeliveryMode = "email" | "push" | "both";

export type NotificationSettings = {
  delivery_mode: DeliveryMode;
  subscription_count: number;
  push_configured: boolean;
  vapid_public_key: string | null;
};

export type PushSubscriptionPayload = {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
};

export type OpsWindow = "24h" | "7d" | "30d";
export type OpsTimeseriesWindow = "24h" | "7d";
export type OpsAdminOverviewWindow = "1h" | "6h" | "24h" | "7d";

export type OpsSummaryResponse = {
  window: OpsWindow;
  totals: {
    actual_calls: number;
    success_calls: number;
    error_calls: number;
    rate_limited_calls: number;
  };
  expected_vs_actual: Record<string, { expected: number; actual: number }>;
  by_provider: Array<{
    provider: string;
    actual_calls: number;
    success_calls: number;
    error_calls: number;
    rate_limited_calls: number;
    expected_calls: number | null;
  }>;
  by_endpoint: Array<{
    provider: string;
    endpoint_key: string;
    actual_calls: number;
    success_calls: number;
    error_calls: number;
    rate_limited_calls: number;
  }>;
};

export type OpsTimeseriesResponse = {
  window: OpsTimeseriesWindow;
  bucket: "hour";
  points: Array<{
    bucket_start: string;
    provider: string;
    actual_calls: number;
    success_calls: number;
    error_calls: number;
    rate_limited_calls: number;
    expected_calls: number | null;
  }>;
};

export type OpsIngestHealthResponse = {
  scheduler_mode: "live" | "pregame_hot" | "pregame_cold" | "off";
  next_run_at: string | null;
  last_success_at: string | null;
  active_leagues: League[];
  states: Array<{
    source_key: string;
    mode: string;
    next_due_at: string | null;
    last_success_at: string | null;
    backoff_until: string | null;
    last_error: string | null;
  }>;
  events: Array<{
    id: number;
    source_key: string;
    event_type: string;
    mode: string | null;
    message: string | null;
    occurred_at: string;
  }>;
};

export type OpsAdminSummaryResponse = {
  overview: {
    window: OpsAdminOverviewWindow;
    total_provider_calls: number;
    provider_errors: number;
    provider_rate_limits: number;
    total_emails_attempted: number;
    emails_sent: number;
    emails_failed: number;
    total_alerts_created: number;
    last_updated_at: string;
  };
  providers: Array<{
    provider: string;
    total_calls: number;
    success_calls: number;
    error_calls: number;
    rate_limited_calls: number;
    calls_per_hour: number;
    quota_limit_window: number | null;
    utilization_pct: number | null;
    most_used_endpoint: string | null;
  }>;
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
    magic_links: {
      attempted: number;
      sent: number;
      failed: number;
    };
    resend: {
      total_calls: number;
      success_calls: number;
      error_calls: number;
      rate_limited_calls: number;
    };
  };
  runtime: {
    scheduler_mode: string;
    next_run_at: string | null;
    last_success_at: string | null;
    active_leagues: League[];
    league_settings: LeagueSetting[];
    jobs: Array<{
      job_type: string;
      league: string | null;
      status: string;
      next_run_at: string | null;
      last_success_at: string | null;
      backoff_until: string | null;
      last_error: string | null;
    }>;
  };
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

export type OpsLeagueSettingsResponse = {
  items: LeagueSetting[];
};
