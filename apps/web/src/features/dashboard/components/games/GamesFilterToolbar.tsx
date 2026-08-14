import { useState } from "react";

import { type League, type LeagueSetting } from "../../../../shared/api";
import { LeagueTabs, ScopeToggle } from "../DashboardFilters";
import { type DayOption, localDateKey } from "./games-view-utils";

export function GamesFilterToolbar({
  activeLeagues,
  leagueFilter,
  onLeagueFilterChange,
  dayFilter,
  onDayFilterChange,
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
      className={`filter-toolbar games-filter-toolbar ${showScopeFilter ? "" : "without-scope"}`.trim()}
      aria-label="Game filters"
    >
      {showScopeFilter ? (
        <ScopeToggle
          ariaLabel="Game scope"
          allLabel="All games"
          value={gameScope}
          followingCount={followedGameCount}
          onChange={onGameScopeChange}
        />
      ) : null}
      <LeagueTabs
        ariaLabel="League"
        options={[
          { value: "all", label: "All", ariaLabel: "All leagues" },
          ...activeLeagues.map(({ league, label }) => ({ value: league, label })),
        ]}
        value={leagueFilter}
        onChange={onLeagueFilterChange}
      />
      <div className="games-date-filter" role="group" aria-label="Game date">
        <button
          className="games-date-step"
          type="button"
          aria-label="Previous date"
          onClick={() => previousDay && onDayFilterChange(previousDay.key)}
          disabled={!previousDay}
        >
          ‹
        </button>
        <select
          className="games-date-select"
          aria-label="Game date"
          value={dayFilter}
          onChange={(event) => onDayFilterChange(event.target.value)}
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
          disabled={!nextDay}
        >
          ›
        </button>
      </div>
    </section>
  );
}
