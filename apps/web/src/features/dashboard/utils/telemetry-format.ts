export function formatRelativeTime(isoTime: string): string {
  const deltaSeconds = Math.floor((Date.now() - new Date(isoTime).getTime()) / 1000);
  const absSeconds = Math.abs(deltaSeconds);
  if (absSeconds < 60) {
    return deltaSeconds <= 0 ? `in ${absSeconds}s` : `${absSeconds}s ago`;
  }
  if (absSeconds < 3600) {
    const minutes = Math.floor(absSeconds / 60);
    return deltaSeconds <= 0 ? `in ${minutes}m` : `${minutes}m ago`;
  }
  if (absSeconds < 86400) {
    const hours = Math.floor(absSeconds / 3600);
    return deltaSeconds <= 0 ? `in ${hours}h` : `${hours}h ago`;
  }
  const days = Math.floor(absSeconds / 86400);
  return deltaSeconds <= 0 ? `in ${days}d` : `${days}d ago`;
}

export function formatElapsedTime(isoTime: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(isoTime).getTime()) / 1000));
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m ago`;
  }
  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)}h ago`;
  }
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function formatNullableNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat().format(value);
}

export function formatHealthStatus(status: "healthy" | "watch" | "at_risk"): string {
  if (status === "at_risk") {
    return "At Risk";
  }
  if (status === "watch") {
    return "Watch";
  }
  return "Healthy";
}

export function severityToBadgeClass(severity: "low" | "medium" | "high"): string {
  if (severity === "high") {
    return "is-danger";
  }
  if (severity === "medium") {
    return "is-warn";
  }
  return "is-ok";
}

export function trendDirectionSymbol(direction: "up" | "down" | "flat"): string {
  if (direction === "up") {
    return "↑";
  }
  if (direction === "down") {
    return "↓";
  }
  return "→";
}

export function formatGameStatusLabel(status: string, isFinal: boolean, fallbackTime: string): string {
  if (status === "in_progress" || status === "live") {
    return `Live • ${fallbackTime}`;
  }
  if (status === "final" || isFinal) {
    return "Final";
  }
  return fallbackTime;
}

export function formatSyncAge(value: Date | null): string {
  if (!value) return "Never";
  const diffMs = Date.now() - value.getTime();
  if (diffMs < 60_000) return "Just now";
  const mins = Math.round(diffMs / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}
