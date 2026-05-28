import { type OpsAdminOverviewResponse, type OpsIngestHealthResponse } from "../../../../shared/api";

import { type AdminTab, type ProviderKey } from "./admin-view-types";

export function dateLabel(isoTime: string | null | undefined): string {
  if (!isoTime) {
    return "n/a";
  }
  const date = new Date(isoTime);
  if (Number.isNaN(date.getTime())) {
    return "n/a";
  }
  return date.toLocaleString();
}

export function titleCaseMode(mode: string | null | undefined): string {
  if (!mode) {
    return "n/a";
  }
  return mode.replace(/_/g, " ");
}

export function compactEventLabel(value: string): string {
  return value.replace(/_/g, " ");
}

export function eventTrendPoints(events: OpsIngestHealthResponse["events"]): number[] {
  const now = Date.now();
  const bucketHours = 6;
  const buckets = Array.from({ length: bucketHours }, () => 0);
  for (const event of events) {
    const diffHours = (now - new Date(event.occurred_at).getTime()) / (1000 * 60 * 60);
    if (diffHours < 0 || diffHours >= bucketHours) {
      continue;
    }
    const idx = bucketHours - 1 - Math.floor(diffHours);
    buckets[idx] += 1;
  }
  return buckets;
}

export function sparklinePath(points: number[], width: number, height: number): string {
  if (points.length === 0) {
    return "";
  }
  const max = Math.max(...points, 1);
  const stepX = points.length > 1 ? width / (points.length - 1) : width;
  return points
    .map((value, idx) => {
      const x = idx * stepX;
      const y = height - (value / max) * height;
      return `${idx === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function normalizeProviderTab(tab: AdminTab): ProviderKey | null {
  if (tab === "espn" || tab === "resend") {
    return tab;
  }
  if (tab === "odds") {
    return "odds";
  }
  return null;
}

export function findProvider(
  providers: OpsAdminOverviewResponse["providers"],
  providerKey: ProviderKey,
): OpsAdminOverviewResponse["providers"][number] | null {
  return providers.find((provider) => provider.provider === providerKey) ?? null;
}
