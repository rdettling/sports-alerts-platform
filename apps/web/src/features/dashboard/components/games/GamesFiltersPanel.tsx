import { type League } from "../../../../shared/api";
import { leagueLabel } from "../../../../shared/lib/dashboard-ui";
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
  activeLeagues: League[];
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
        <button className={`chip-btn ${leagueFilter === "all" ? "active" : ""}`.trim()} onClick={() => onLeagueFilterChange("all")} disabled={isLoading}>All</button>
        {activeLeagues.map((league) => (
          <button key={league} className={`chip-btn ${leagueFilter === league ? "active" : ""}`.trim()} onClick={() => onLeagueFilterChange(league)} disabled={isLoading}>{leagueLabel(league)}</button>
        ))}
      </div>
      <button className={`games-day-filter-btn ${dayFilter === "all" ? "active" : ""}`.trim()} onClick={() => onDayFilterChange("all")} disabled={isLoading}>
        <span>All</span>
        <span className="muted">{totalLeagueGames}</span>
      </button>
      {dayOptions.map((day) => (
        <button key={day.key} className={`games-day-filter-btn ${dayFilter === day.key ? "active" : ""}`.trim()} onClick={() => onDayFilterChange(day.key)} disabled={isLoading}>
          <span>{day.label}</span>
          <span className="muted">{day.count}</span>
        </button>
      ))}
    </aside>
  );
}
