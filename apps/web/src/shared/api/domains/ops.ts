import { apiRequest } from "../client";
import type {
  CompetitionSetting,
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

export function updateOpsCompetitionSetting(
  token: string,
  competition: CompetitionSetting["competition"],
  isEnabled: boolean,
): Promise<CompetitionSetting> {
  return apiRequest<CompetitionSetting>(`/ops/competitions/${competition}`, {
    method: "PUT",
    token,
    body: JSON.stringify({ is_enabled: isEnabled }),
  });
}
