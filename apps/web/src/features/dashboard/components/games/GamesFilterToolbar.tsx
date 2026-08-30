import { type ReactNode, useState } from "react";

import { type Competition, type CompetitionSetting } from "../../../../shared/api";
import { CompetitionTabs, ConferenceSelect, ScopeToggle } from "../DashboardFilters";
import {
  type DayOption,
  type GameSortMode,
  localDateKey,
  supportsGameSorting,
} from "./games-view-utils";

export function GamesFilterToolbar({
  activeCompetitions,
  competitionFilter,
  onCompetitionFilterChange,
  dayFilter,
  onDayFilterChange,
  dayOptions,
  sortMode,
  onSortModeChange,
  showScopeFilter,
  gameScope,
  onGameScopeChange,
  followedGameCount,
  conferenceOptions,
  conferenceFilter,
  onConferenceFilterChange,
  competitionVisibilityControl,
}: {
  activeCompetitions: CompetitionSetting[];
  competitionFilter: "all" | Competition;
  onCompetitionFilterChange: (value: "all" | Competition) => void;
  dayFilter: string | null;
  onDayFilterChange: (value: string) => void;
  dayOptions: DayOption[];
  sortMode: GameSortMode;
  onSortModeChange: (value: GameSortMode) => void;
  showScopeFilter: boolean;
  gameScope: "all" | "following";
  onGameScopeChange: (value: "all" | "following") => void;
  followedGameCount: number;
  conferenceOptions: string[];
  conferenceFilter: "all" | string;
  onConferenceFilterChange: (value: "all" | string) => void;
  competitionVisibilityControl?: ReactNode;
}) {
  const selectedDayIndex = dayOptions.findIndex((day) => day.key === dayFilter);
  const [todayKey] = useState(() => localDateKey(new Date(Date.now()).toISOString()));
  const previousDay = selectedDayIndex > 0 ? dayOptions[selectedDayIndex - 1] : null;
  const nextDay =
    selectedDayIndex >= 0 && selectedDayIndex < dayOptions.length - 1
      ? dayOptions[selectedDayIndex + 1]
      : null;
  const showSort = supportsGameSorting(competitionFilter);

  return (
    <section
      className={`filter-toolbar games-filter-toolbar ${showScopeFilter ? "" : "without-scope"} ${competitionFilter === "FBS" ? "with-conference" : ""} ${showSort ? "with-sort" : ""}`.trim()}
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
      <div className="competition-filter-row">
        <CompetitionTabs
          ariaLabel="Competition"
          options={[
            { value: "all", label: "All", ariaLabel: "All competitions" },
            ...activeCompetitions.map(({ competition, label }) => ({ value: competition, label })),
          ]}
          value={competitionFilter}
          onChange={onCompetitionFilterChange}
        />
        {competitionVisibilityControl}
      </div>
      {competitionFilter === "FBS" ? (
        <ConferenceSelect
          options={conferenceOptions}
          value={conferenceFilter}
          onChange={onConferenceFilterChange}
        />
      ) : null}
      <div className={`games-order-controls ${showSort ? "with-sort" : ""}`.trim()}>
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
            value={dayFilter ?? ""}
            onChange={(event) => onDayFilterChange(event.target.value)}
            disabled={dayOptions.length === 0}
          >
            {dayOptions.length === 0 ? <option value="">No dates</option> : null}
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
        {showSort ? (
          <select
            className="games-sort-select"
            aria-label="Game sort"
            value={sortMode}
            onChange={(event) => onSortModeChange(event.target.value as GameSortMode)}
          >
            <option value="start_time">Start time</option>
            <option value="ending_soon">Ending soon</option>
            <option value="watchability">Watchability</option>
          </select>
        ) : null}
      </div>
    </section>
  );
}
