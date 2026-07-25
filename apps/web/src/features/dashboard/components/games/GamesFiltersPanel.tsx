import { type League, type LeagueSetting } from "../../../../shared/api";
import { type DayOption } from "./games-view-utils";

type LeagueSyncItem = {
  label: string;
  value: string;
  tone: "fresh" | "stale" | "idle";
};

function compactAgeLabel(value: string): string {
  return value.replace(" ago", "");
}

export function GamesFiltersPanel({
  activeLeagues,
  leagueFilter,
  onLeagueFilterChange,
  dayFilter,
  onDayFilterChange,
  isLoading,
  totalLeagueGames,
  dayOptions,
  syncItems,
  showScopeFilter,
  gameScope,
  onGameScopeChange,
  followedGameCount,
}: {
  activeLeagues: LeagueSetting[];
  leagueFilter: "all" | League;
  onLeagueFilterChange: (value: "all" | League) => void;
  dayFilter: "all" | string;
  onDayFilterChange: (value: "all" | string) => void;
  isLoading: boolean;
  totalLeagueGames: number;
  dayOptions: DayOption[];
  syncItems: LeagueSyncItem[];
  showScopeFilter: boolean;
  gameScope: "all" | "following";
  onGameScopeChange: (value: "all" | "following") => void;
  followedGameCount: number;
}) {
  const syncByLabel = new Map(syncItems.map((item) => [item.label, item]));
  const leagueOptions = activeLeagues.map((league) => ({
    ...league,
    syncItem: syncByLabel.get(league.label),
  }));

  return (
    <aside className="games-day-filter">
      {showScopeFilter ? (
        <div className="games-scope-filter" aria-label="Game scope">
          <button
            className={`games-scope-filter-btn ${gameScope === "all" ? "active" : ""}`.trim()}
            type="button"
            onClick={() => onGameScopeChange("all")}
          >
            All games
          </button>
          <button
            className={`games-scope-filter-btn ${gameScope === "following" ? "active" : ""}`.trim()}
            type="button"
            onClick={() => onGameScopeChange("following")}
          >
            Following <span>{followedGameCount}</span>
          </button>
        </div>
      ) : null}
      <div className="games-league-filter" role="tablist" aria-label="League filter">
        <button
          className={`games-league-filter-btn ${leagueFilter === "all" ? "active" : ""}`.trim()}
          type="button"
          aria-label="All leagues"
          onClick={() => onLeagueFilterChange("all")}
          disabled={isLoading}
        >
          <span className="games-league-filter-label">All</span>
        </button>
        {leagueOptions.map(({ league, label, syncItem }) => (
          <button
            key={league}
            className={`games-league-filter-btn ${leagueFilter === league ? "active" : ""} ${syncItem ? `tone-${syncItem.tone}` : ""}`.trim()}
            type="button"
            onClick={() => onLeagueFilterChange(league)}
            disabled={isLoading}
          >
            <span className="games-league-filter-label">{label}</span>
            <span className="games-league-filter-meta">{syncItem ? compactAgeLabel(syncItem.value) : "Sync pending"}</span>
          </button>
        ))}
      </div>
      <button
        className={`games-day-filter-btn ${dayFilter === "all" ? "active" : ""}`.trim()}
        type="button"
        aria-label="All days"
        onClick={() => onDayFilterChange("all")}
        disabled={isLoading}
      >
        <span>All</span>
        <span className="muted">{totalLeagueGames}</span>
      </button>
      {dayOptions.map((day) => (
        <button key={day.key} className={`games-day-filter-btn ${dayFilter === day.key ? "active" : ""}`.trim()} type="button" onClick={() => onDayFilterChange(day.key)} disabled={isLoading}>
          <span>{day.label}</span>
          <span className="muted">{day.count}</span>
        </button>
      ))}
    </aside>
  );
}
