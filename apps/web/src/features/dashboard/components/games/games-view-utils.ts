import { type Game, type League, type Sport } from "../../../../shared/api";
import { formatGameTime } from "../../../../shared/lib/dashboard-ui";
import { formatGameStatusLabel } from "../../utils/telemetry-format";

export type GameDayGroup = { label: string; items: Game[] };

export type DayOption = { key: string; label: string; count: number };

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
  return games.filter((game) => game.league === leagueFilter);
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

export function gameStatusLabel(game: Game, sport: Sport): string {
  return formatGameStatusLabel(
    game.status,
    game.status === "final" || game.is_final,
    formatGameTime(game, sport),
  );
}
