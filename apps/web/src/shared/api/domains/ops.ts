import { apiRequest } from "../client";
import type {
  LeagueSetting,
  OpsAdminSummaryResponse,
  OpsAdminOverviewWindow,
  OpsNeonUsageResponse,
} from "../types";

export function getOpsAdminSummary(
  token: string,
  window: OpsAdminOverviewWindow,
): Promise<OpsAdminSummaryResponse> {
  return apiRequest<OpsAdminSummaryResponse>(
    `/ops/admin/summary?window=${encodeURIComponent(window)}`,
    { token },
  );
}

export function getOpsNeonUsage(token: string): Promise<OpsNeonUsageResponse> {
  return apiRequest<OpsNeonUsageResponse>("/ops/db/neon-usage", { token });
}

export function updateOpsLeagueSetting(
  token: string,
  league: LeagueSetting["league"],
  isEnabled: boolean,
): Promise<LeagueSetting> {
  return apiRequest<LeagueSetting>(`/ops/leagues/${league}`, {
    method: "PUT",
    token,
    body: JSON.stringify({ is_enabled: isEnabled }),
  });
}
