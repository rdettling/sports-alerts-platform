const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!API_BASE_URL) {
  throw new Error("Missing required env var: VITE_API_BASE_URL");
}

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: { id: number; email: string; role: "user" | "admin"; created_at: string };
};

export type MagicLinkStartResponse = {
  message: string;
};

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
  odds: {
    home_moneyline: number | null;
    away_moneyline: number | null;
    bookmaker: string | null;
    last_update: string | null;
  } | null;
};

export type CurrentFollows = {
  teams: Team[];
  games: Game[];
};

export type AlertPreference = {
  alert_type: string;
  is_enabled: boolean;
  close_game_margin_threshold: number | null;
  close_game_time_threshold_seconds: number | null;
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

export type AlertType = "game_start" | "close_game_late" | "final_result";
export type DeliveryStatus = "pending" | "sent" | "failed";

export type OpsWindow = "24h" | "7d" | "30d";
export type OpsTimeseriesWindow = "24h" | "7d";

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

export type OpsIngestRunsResponse = {
  items: Array<{
    ingest_run_id: number;
    started_at: string;
    completed_at: string | null;
    cycle_duration_seconds: number | null;
    status: string;
    poll_mode: string | null;
    games_checked: number;
    games_updated: number;
    expected_espn_calls: number;
    actual_espn_calls: number;
    expected_odds_calls: number;
    actual_odds_calls: number;
  }>;
};

function normalizeErrorDetail(detail: unknown): string {
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") {
          return item.msg;
        }
        return null;
      })
      .filter((message): message is string => Boolean(message));
    if (messages.length > 0) {
      return messages.join(", ");
    }
  }

  return "Request failed";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    });
  } catch {
    throw new Error(`Unable to reach API at ${API_BASE_URL}. Make sure the API service is running.`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(normalizeErrorDetail(body.detail));
  }
  return response.json() as Promise<T>;
}

export function startMagicLink(email: string): Promise<MagicLinkStartResponse> {
  return request<MagicLinkStartResponse>("/auth/magic-link/start", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function verifyMagicLink(token: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/magic-link/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function me(token: string) {
  return request<UserProfile>("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export function listTeams(): Promise<Team[]> {
  return request<Team[]>("/teams");
}

export function listGames(): Promise<Game[]> {
  return request<Game[]>("/games");
}

export function listFollows(token: string): Promise<CurrentFollows> {
  return request<CurrentFollows>("/follows", { headers: authHeaders(token) });
}

export function followTeam(token: string, teamId: number): Promise<{ status: string }> {
  return request<{ status: string }>(`/follows/teams/${teamId}`, { method: "POST", headers: authHeaders(token) });
}

export function unfollowTeam(token: string, teamId: number): Promise<{ status: string }> {
  return request<{ status: string }>(`/follows/teams/${teamId}`, { method: "DELETE", headers: authHeaders(token) });
}

export function followGame(token: string, gameId: number): Promise<{ status: string }> {
  return request<{ status: string }>(`/follows/games/${gameId}`, { method: "POST", headers: authHeaders(token) });
}

export function unfollowGame(token: string, gameId: number): Promise<{ status: string }> {
  return request<{ status: string }>(`/follows/games/${gameId}`, { method: "DELETE", headers: authHeaders(token) });
}

export function listAlertPreferences(token: string): Promise<AlertPreference[]> {
  return request<AlertPreference[]>("/alert-preferences", { headers: authHeaders(token) });
}

export function updateAlertPreference(
  token: string,
  alertType: string,
  payload: {
    is_enabled?: boolean;
    close_game_margin_threshold?: number;
    close_game_time_threshold_seconds?: number;
  },
): Promise<AlertPreference> {
  return request<AlertPreference>(`/alert-preferences/${alertType}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export function listAlertHistory(
  token: string,
  options?: { alertType?: AlertType; sinceHours?: number; limit?: number },
): Promise<{ items: AlertHistoryItem[] }> {
  const params = new URLSearchParams();
  if (options?.alertType) {
    params.set("alert_type", options.alertType);
  }
  if (options?.sinceHours) {
    params.set("since_hours", String(options.sinceHours));
  }
  if (options?.limit) {
    params.set("limit", String(options.limit));
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<{ items: AlertHistoryItem[] }>(`/alerts/history${suffix}`, {
    headers: authHeaders(token),
  });
}

export function sendDevTestEmail(
  token: string,
  payload: { alert_type: AlertType },
): Promise<{ id: number; game_id: number; alert_type: AlertType; delivery_status: DeliveryStatus }> {
  return request<{ id: number; game_id: number; alert_type: AlertType; delivery_status: DeliveryStatus }>(
    "/alerts/admin/test-email",
    {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify(payload),
    },
  );
}

export function getOpsApiUsageSummary(token: string, window: OpsWindow): Promise<OpsSummaryResponse> {
  return request<OpsSummaryResponse>(`/ops/api-usage/summary?window=${encodeURIComponent(window)}`, {
    headers: authHeaders(token),
  });
}

export function getOpsApiUsageTimeseries(token: string, window: OpsTimeseriesWindow): Promise<OpsTimeseriesResponse> {
  return request<OpsTimeseriesResponse>(
    `/ops/api-usage/timeseries?window=${encodeURIComponent(window)}&bucket=hour`,
    {
      headers: authHeaders(token),
    },
  );
}

export function getOpsApiUsageIngestRuns(token: string, limit: number = 50): Promise<OpsIngestRunsResponse> {
  return request<OpsIngestRunsResponse>(`/ops/api-usage/ingest-runs?limit=${encodeURIComponent(String(limit))}`, {
    headers: authHeaders(token),
  });
}
