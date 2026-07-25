import { useState } from "react";

import { type League, type LeagueSetting } from "../../../../shared/api";
import { type DayOption, localDateKey } from "./games-view-utils";

export function GamesFilterToolbar({
  activeLeagues,
  leagueFilter,
  onLeagueFilterChange,
  dayFilter,
  onDayFilterChange,
  isLoading,
  totalLeagueGames,
  dayOptions,
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
  showScopeFilter: boolean;
  gameScope: "all" | "following";
  onGameScopeChange: (value: "all" | "following") => void;
  followedGameCount: number;
}) {
  const selectedDayIndex = dayOptions.findIndex((day) => day.key === dayFilter);
  const [todayKey] = useState(() => localDateKey(new Date(Date.now()).toISOString()));
  const previousDay = selectedDayIndex > 0 ? dayOptions[selectedDayIndex - 1] : null;
  const nextDay =
    selectedDayIndex >= 0 && selectedDayIndex < dayOptions.length - 1
      ? dayOptions[selectedDayIndex + 1]
      : null;

  return (
    <section
      className={`games-filter-toolbar ${showScopeFilter ? "" : "without-scope"}`.trim()}
      aria-label="Game filters"
    >
      {showScopeFilter ? (
        <div className="games-scope-filter" role="group" aria-label="Game scope">
          <button
            className={`games-scope-filter-btn ${gameScope === "all" ? "active" : ""}`.trim()}
            type="button"
            aria-pressed={gameScope === "all"}
            onClick={() => onGameScopeChange("all")}
          >
            All games
          </button>
          <button
            className={`games-scope-filter-btn ${gameScope === "following" ? "active" : ""}`.trim()}
            type="button"
            aria-pressed={gameScope === "following"}
            onClick={() => onGameScopeChange("following")}
          >
            Following <span>{followedGameCount}</span>
          </button>
        </div>
      ) : null}
      <div className="games-league-filter" role="group" aria-label="League">
        <button
          className={`games-league-filter-btn ${leagueFilter === "all" ? "active" : ""}`.trim()}
          type="button"
          aria-label="All leagues"
          aria-pressed={leagueFilter === "all"}
          onClick={() => onLeagueFilterChange("all")}
          disabled={isLoading}
        >
          All
        </button>
        {activeLeagues.map(({ league, label }) => (
          <button
            key={league}
            className={`games-league-filter-btn ${leagueFilter === league ? "active" : ""}`.trim()}
            type="button"
            aria-pressed={leagueFilter === league}
            onClick={() => onLeagueFilterChange(league)}
            disabled={isLoading}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="games-date-filter" role="group" aria-label="Game date">
        <button
          className="games-date-step"
          type="button"
          aria-label="Previous date"
          onClick={() => previousDay && onDayFilterChange(previousDay.key)}
          disabled={isLoading || !previousDay}
        >
          ‹
        </button>
        <select
          className="games-date-select"
          aria-label="Game date"
          value={dayFilter}
          onChange={(event) => onDayFilterChange(event.target.value)}
          disabled={isLoading}
        >
          <option value="all">All dates ({totalLeagueGames})</option>
          {dayOptions.map((day) => (
            <option key={day.key} value={day.key}>
              {day.key === todayKey ? "Today" : day.label} ({day.count})
            </option>
          ))}
        </select>
        <button
          className="games-date-step"
          type="button"
          aria-label="Next date"
          onClick={() => nextDay && onDayFilterChange(nextDay.key)}
          disabled={isLoading || !nextDay}
        >
          ›
        </button>
      </div>
    </section>
  );
}
