import { type Game, type League } from "../../../../shared/api";
import { formatGameTime } from "../../../../shared/lib/dashboard-ui";
import { formatGameStatusLabel } from "../../utils/telemetry-format";

export type SyncTone = "fresh" | "stale" | "idle";

export type GameDayGroup = { label: string; items: Game[] };

export type DayOption = { key: string; label: string; count: number };

export type SyncRow = {
  key: string;
  label: string;
  cadenceLabel: string;
  lastAt: Date | null;
  detail: string;
  tone: SyncTone;
};

export function localDateKey(dateIso: string): string {
  const value = new Date(dateIso);
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function sortGamesByStart(games: Game[]): Game[] {
  return [...games].sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime());
}

export function filterGamesByLeague(games: Game[], leagueFilter: "all" | League): Game[] {
  if (leagueFilter === "all") return games;
  return games.filter((game) => (game.league || "").toUpperCase() === leagueFilter);
}

export function buildDayOptions(games: Game[]): DayOption[] {
  const map = new Map<string, DayOption>();
  games.forEach((game) => {
    const key = localDateKey(game.scheduled_start_time);
    const label = new Date(game.scheduled_start_time).toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
    const current = map.get(key);
    if (current) current.count += 1;
    else map.set(key, { key, label, count: 1 });
  });
  return Array.from(map.values());
}

export function filterGamesByDay(games: Game[], dayFilter: "all" | string): Game[] {
  if (dayFilter === "all") return games;
  return games.filter((game) => localDateKey(game.scheduled_start_time) === dayFilter);
}

export function groupGamesByDay(games: Game[]): GameDayGroup[] {
  const groups = new Map<string, Game[]>();
  games.forEach((game) => {
    const label = new Date(game.scheduled_start_time).toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
    const current = groups.get(label) ?? [];
    current.push(game);
    groups.set(label, current);
  });
  return Array.from(groups.entries()).map(([label, items]) => ({ label, items }));
}

function syncTone(lastAt: Date | null, maxStaleMinutes: number, active: boolean): SyncTone {
  if (!lastAt) return "stale";
  if (!active) return "idle";
  const ageMinutes = (Date.now() - lastAt.getTime()) / 60_000;
  return ageMinutes <= maxStaleMinutes ? "fresh" : "stale";
}

function latestIngestAt(games: Game[]): Date | null {
  const lastMs = games
    .map((game) => (game.last_ingested_at ? new Date(game.last_ingested_at).getTime() : Number.NaN))
    .filter((ts) => !Number.isNaN(ts))
    .reduce((max, ts) => Math.max(max, ts), 0);
  return lastMs > 0 ? new Date(lastMs) : null;
}

export function latestIngestAtFromGames(games: Game[]): Date | null {
  return latestIngestAt(games);
}

export function buildSyncRows(games: Game[], activeLeagues: League[]): SyncRow[] {
  const byLeague = (league: League) => {
    const leagueGames = games.filter((game) => (game.league || "").toUpperCase() === league);
    const liveCount = leagueGames.filter((game) => game.status === "in_progress" || game.status === "live").length;
    const nextStartMs = leagueGames
      .filter((game) => game.status === "scheduled")
      .map((game) => new Date(game.scheduled_start_time).getTime())
      .filter((ts) => !Number.isNaN(ts))
      .sort((a, b) => a - b)[0];
    return { liveCount, nextStartMs, lastAt: latestIngestAt(leagueGames) };
  };

  const catalogLastAt = latestIngestAt(games);

  const leagueRow = (
    label: string,
    cadenceLabel: string,
    info: { liveCount: number; nextStartMs?: number; lastAt: Date | null },
    staleAfterMinutes: number,
  ): SyncRow => {
    const active = info.liveCount > 0;
    const detail = active
      ? `${info.liveCount} live`
      : info.nextStartMs
        ? `Next ${new Date(info.nextStartMs).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`
        : "No upcoming";
    return {
      key: label,
      label,
      cadenceLabel,
      lastAt: info.lastAt,
      detail,
      tone: syncTone(info.lastAt, staleAfterMinutes, active),
    };
  };

  return [
    {
      key: "catalog",
      label: "Catalog",
      cadenceLabel: "12h cadence",
      lastAt: catalogLastAt,
      detail: "Schedule + odds snapshot",
      tone: syncTone(catalogLastAt, 12 * 60 + 30, true),
    },
    ...activeLeagues.map((league) =>
      leagueRow(
        `Live (${league})`,
        league === "NBA" ? "2m cadence" : "5m cadence",
        byLeague(league),
        league === "NBA" ? 4 : 10,
      ),
    ),
  ];
}

export function gameStatusLabel(game: Game): string {
  return formatGameStatusLabel(
    game.status,
    game.status === "final" || game.is_final,
    formatGameTime(game),
  );
}
