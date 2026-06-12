import { apiRequest } from "../client";
import type {
  LeagueSetting,
  OpsAdminOverviewResponse,
  OpsAdminOverviewWindow,
  OpsIngestHealthResponse,
  OpsLeagueSettingsResponse,
  OpsNeonUsageResponse,
  OpsSummaryResponse,
  OpsTimeseriesResponse,
  OpsTimeseriesWindow,
  OpsWindow,
} from "../types";

export function getOpsApiUsageSummary(token: string, window: OpsWindow): Promise<OpsSummaryResponse> {
  return apiRequest<OpsSummaryResponse>(`/ops/api-usage/summary?window=${encodeURIComponent(window)}`, { token });
}

export function getOpsApiUsageTimeseries(token: string, window: OpsTimeseriesWindow): Promise<OpsTimeseriesResponse> {
  return apiRequest<OpsTimeseriesResponse>(`/ops/api-usage/timeseries?window=${encodeURIComponent(window)}&bucket=hour`, { token });
}

export function getOpsIngestHealth(token: string, eventLimit: number = 20): Promise<OpsIngestHealthResponse> {
  return apiRequest<OpsIngestHealthResponse>(`/ops/db/ingest-health?event_limit=${encodeURIComponent(String(eventLimit))}`, {
    token,
  });
}

export function getOpsAdminOverview(
  token: string,
  window: OpsAdminOverviewWindow,
  options?: { provider?: string; limit?: number },
): Promise<OpsAdminOverviewResponse> {
  const params = new URLSearchParams();
  params.set("window", window);
  if (options?.provider) params.set("provider", options.provider);
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  return apiRequest<OpsAdminOverviewResponse>(`/ops/admin/overview?${params.toString()}`, { token });
}

export function getOpsNeonUsage(token: string): Promise<OpsNeonUsageResponse> {
  return apiRequest<OpsNeonUsageResponse>("/ops/db/neon-usage", { token });
}

export function getOpsLeagueSettings(token: string): Promise<OpsLeagueSettingsResponse> {
  return apiRequest<OpsLeagueSettingsResponse>("/ops/leagues", { token });
}

export function updateOpsLeagueSetting(token: string, league: LeagueSetting["league"], isEnabled: boolean): Promise<LeagueSetting> {
  return apiRequest<LeagueSetting>(`/ops/leagues/${league}`, {
    method: "PUT",
    token,
    body: JSON.stringify({ is_enabled: isEnabled }),
  });
}
