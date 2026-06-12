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

export type Team = {
  id: number;
  external_team_id: string;
  league: string;
  name: string;
  abbreviation: string;
};

export type Game = {
  id: number;
  external_game_id: string;
  league: string;
  home_team_id: number;
  away_team_id: number;
  scheduled_start_time: string;
  status: string;
  home_score: number | null;
  away_score: number | null;
  period: number | null;
  clock: string | null;
  is_final: boolean;
  last_ingested_at: string | null;
  odds: {
    home_moneyline: number | null;
    away_moneyline: number | null;
    bookmaker: string | null;
    last_update: string | null;
  } | null;
};

export type League = "NBA" | "MLB" | "WORLD_CUP";
export type LeagueSetting = {
  league: League;
  label: string;
  badge_label: string;
  alert_types: AlertType[];
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
  delivery_channel: string;
  delivery_status: string;
  sent_at: string;
  provider_message_id: string | null;
  metadata_json: Record<string, unknown> | null;
  game_external_id: string;
  home_team_abbreviation: string;
  away_team_abbreviation: string;
};

export type AlertType = "game_start" | "close_game_late" | "inning_start" | "final_result";
export type DeliveryStatus = "pending" | "sent" | "failed";

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

export type OpsAdminOverviewResponse = {
  global_health: {
    status: "healthy" | "watch" | "at_risk";
    providers_at_risk: number;
    providers_on_watch: number;
  };
  thresholds: {
    utilization_watch_pct: number;
    utilization_risk_pct: number;
    error_watch_pct: number;
    error_risk_pct: number;
  };
  risk_cards: Array<{ key: string; label: string; value: number; status: "ok" | "medium" | "high" }>;
  providers: Array<{
    provider: string;
    quota_limit_24h: number | null;
    quota_limit_window: number | null;
    total_calls: number;
    success_calls: number;
    error_calls: number;
    rate_limited_calls: number;
    utilization_pct: number | null;
    remaining_budget: number | null;
    calls_per_hour: number;
    error_pct: number;
    trend_delta_calls: number;
    trend_direction: "up" | "down" | "flat";
    status: "healthy" | "watch" | "at_risk";
    reasons: string[];
  }>;
  incidents: Array<{
    id: string;
    occurred_at: string;
    provider: string | null;
    type: string;
    severity: "low" | "medium" | "high";
    title: string;
    detail: string;
  }>;
  meta: { last_updated_at: string; window: OpsAdminOverviewWindow };
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
