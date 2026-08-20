import { useState } from "react";

import { type Competition, type CompetitionSetting } from "../../../../shared/api";
import { CompetitionTabs, ScopeToggle } from "../DashboardFilters";
import { type DayOption, localDateKey } from "./games-view-utils";

export function GamesFilterToolbar({
  activeCompetitions,
  competitionFilter,
  onCompetitionFilterChange,
  dayFilter,
  onDayFilterChange,
  totalCompetitionGames,
  dayOptions,
  showScopeFilter,
  gameScope,
  onGameScopeChange,
  followedGameCount,
}: {
  activeCompetitions: CompetitionSetting[];
  competitionFilter: "all" | Competition;
  onCompetitionFilterChange: (value: "all" | Competition) => void;
  dayFilter: "all" | string;
  onDayFilterChange: (value: "all" | string) => void;
  totalCompetitionGames: number;
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
      <CompetitionTabs
        ariaLabel="Competition"
        options={[
          { value: "all", label: "All", ariaLabel: "All competitions" },
          ...activeCompetitions.map(({ competition, label }) => ({ value: competition, label })),
        ]}
        value={competitionFilter}
        onChange={onCompetitionFilterChange}
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
          <option value="all">All dates ({totalCompetitionGames})</option>
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
