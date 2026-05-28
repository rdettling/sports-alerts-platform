import { type DayOption } from "./games-view-utils";

export function GamesFiltersPanel({
  leagueFilter,
  onLeagueFilterChange,
  dayFilter,
  onDayFilterChange,
  isLoading,
  totalLeagueGames,
  dayOptions,
}: {
  leagueFilter: "all" | "NBA" | "MLB";
  onLeagueFilterChange: (value: "all" | "NBA" | "MLB") => void;
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
        <button className={`chip-btn ${leagueFilter === "NBA" ? "active" : ""}`.trim()} onClick={() => onLeagueFilterChange("NBA")} disabled={isLoading}>NBA</button>
        <button className={`chip-btn ${leagueFilter === "MLB" ? "active" : ""}`.trim()} onClick={() => onLeagueFilterChange("MLB")} disabled={isLoading}>MLB</button>
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
