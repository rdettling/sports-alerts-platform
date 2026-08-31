import { type Competition, type Game } from "../../../../shared/api";
import {
  liveGameRemainingShare,
  liveGameStagePriority,
  liveWatchabilityScore,
  pregameMatchupPriority,
} from "./game-watchability";

export type DayOption = { key: string; label: string; count: number };
export const GAME_SORT_OPTIONS = [
  { value: "live_first", label: "Live first" },
  { value: "start_time", label: "Start time" },
  { value: "ending_soon", label: "Ending soon" },
  { value: "watchability", label: "Watchability" },
] as const;
export type GameSortMode = (typeof GAME_SORT_OPTIONS)[number]["value"];
export const DEFAULT_GAME_SORT_MODE: GameSortMode = GAME_SORT_OPTIONS[0].value;

export function localDateKey(dateIso: string): string {
  const value = new Date(dateIso);
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function sortGamesByStart(games: Game[]): Game[] {
  return [...games].sort(compareKickoffAscending);
}

export function filterGamesByCompetition(
  games: Game[],
  competitionFilter: "all" | Competition,
): Game[] {
  if (competitionFilter === "all") return games;
  return games.filter((game) => game.competition === competitionFilter);
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
  return Array.from(map.values()).sort((a, b) => a.key.localeCompare(b.key));
}

export function filterGamesByDay(games: Game[], dayFilter: string | null): Game[] {
  if (dayFilter === null) return [];
  return games.filter((game) => localDateKey(game.scheduled_start_time) === dayFilter);
}

export function resolveSelectedDay(
  dayOptions: DayOption[],
  selectedDay: string | null,
  todayKey: string,
): string | null {
  if (dayOptions.length === 0) return null;
  if (selectedDay && dayOptions.some((day) => day.key === selectedDay)) return selectedDay;

  if (selectedDay) {
    const selectedTime = dateKeyTime(selectedDay);
    return [...dayOptions].sort((a, b) => {
      const aTime = dateKeyTime(a.key);
      const bTime = dateKeyTime(b.key);
      return Math.abs(aTime - selectedTime) - Math.abs(bTime - selectedTime) || bTime - aTime;
    })[0].key;
  }

  const today = dayOptions.find((day) => day.key === todayKey);
  if (today) return today.key;
  return dayOptions.find((day) => day.key > todayKey)?.key ?? dayOptions[dayOptions.length - 1].key;
}

export function sortGames(games: Game[], mode: GameSortMode): Game[] {
  if (mode === "start_time") return sortGamesByStart(games);

  return [...games].sort((a, b) => {
    const statusDifference = gameSortStatusRank(a) - gameSortStatusRank(b);
    if (statusDifference !== 0) return statusDifference;

    if (isLiveGame(a) && isLiveGame(b)) {
      const aRemaining = liveGameRemainingShare(a);
      const bRemaining = liveGameRemainingShare(b);
      const aWatchability = liveWatchabilityScore(a);
      const bWatchability = liveWatchabilityScore(b);

      if (mode === "live_first" || mode === "watchability") {
        const watchabilityDifference = compareNullableDescending(aWatchability, bWatchability);
        if (watchabilityDifference !== 0) return watchabilityDifference;
        const stageDifference = liveGameStagePriority(b) - liveGameStagePriority(a);
        if (stageDifference !== 0) return stageDifference;
        const remainingDifference = compareNullableAscending(aRemaining, bRemaining);
        if (remainingDifference !== 0) return remainingDifference;
      } else {
        const remainingDifference = compareNullableAscending(aRemaining, bRemaining);
        if (remainingDifference !== 0) return remainingDifference;
        const watchabilityDifference = compareNullableDescending(aWatchability, bWatchability);
        if (watchabilityDifference !== 0) return watchabilityDifference;
      }
    }

    if (mode === "watchability" && a.status === "scheduled" && b.status === "scheduled") {
      const matchupDifference = pregameMatchupPriority(b) - pregameMatchupPriority(a);
      if (matchupDifference !== 0) return matchupDifference;
      return compareKickoffAscending(a, b);
    }

    return isFinalGame(a) && isFinalGame(b)
      ? compareKickoffDescending(a, b)
      : compareKickoffAscending(a, b);
  });
}

function dateKeyTime(key: string): number {
  const [year, month, day] = key.split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

function isLiveGame(game: Game): boolean {
  return !game.is_final && (game.status === "in_progress" || game.status === "live");
}

function isFinalGame(game: Game): boolean {
  return game.is_final || game.status === "final";
}

function gameSortStatusRank(game: Game): number {
  if (isLiveGame(game)) return 0;
  if (game.status === "scheduled") return 1;
  if (isFinalGame(game)) return 2;
  return 3;
}

function kickoffTime(game: Game): number {
  return new Date(game.scheduled_start_time).getTime();
}

function compareKickoffAscending(a: Game, b: Game): number {
  return kickoffTime(a) - kickoffTime(b) || a.id - b.id;
}

function compareKickoffDescending(a: Game, b: Game): number {
  return kickoffTime(b) - kickoffTime(a) || a.id - b.id;
}

function compareNullableAscending(a: number | null, b: number | null): number {
  if (a === null) return b === null ? 0 : 1;
  if (b === null) return -1;
  return a - b;
}

function compareNullableDescending(a: number | null, b: number | null): number {
  if (a === null) return b === null ? 0 : 1;
  if (b === null) return -1;
  return b - a;
}
