import { type League, type LeagueSetting } from "../../../../shared/api";
import { type DayOption } from "./games-view-utils";

export function GamesFiltersPanel({
  activeLeagues,
  leagueFilter,
  onLeagueFilterChange,
  dayFilter,
  onDayFilterChange,
  isLoading,
  totalLeagueGames,
  dayOptions,
}: {
  activeLeagues: LeagueSetting[];
  leagueFilter: "all" | League;
  onLeagueFilterChange: (value: "all" | League) => void;
  dayFilter: "all" | string;
  onDayFilterChange: (value: "all" | string) => void;
  isLoading: boolean;
  totalLeagueGames: number;
  dayOptions: DayOption[];
}) {
  return (
    <aside className="games-day-filter">
      <div className="games-league-filter" role="tablist" aria-label="League filter">
        <button
          className={`games-league-filter-btn ${leagueFilter === "all" ? "active" : ""}`.trim()}
          type="button"
          aria-label="All leagues"
          onClick={() => onLeagueFilterChange("all")}
          disabled={isLoading}
        >
          All
        </button>
        {activeLeagues.map((league) => (
          <button
            key={league.league}
            className={`games-league-filter-btn ${leagueFilter === league.league ? "active" : ""}`.trim()}
            type="button"
            onClick={() => onLeagueFilterChange(league.league)}
            disabled={isLoading}
          >
            {league.label}
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
