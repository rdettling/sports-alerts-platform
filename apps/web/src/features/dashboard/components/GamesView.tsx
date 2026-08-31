import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { followGame, type Competition, type Team, unfollowGame } from "../../../shared/api";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { useGamesData } from "../hooks/useGamesData";
import { dashboardQueryKeys } from "../hooks/dashboard-query-options";
import { useGameAlertSettings } from "../hooks/useGameAlertSettings";
import { GameAlertSettingsModal } from "./GameAlertSettingsModal";
import { GameScoreRow } from "./GameScoreRow";
import { fbsConferenceOptions } from "./fbs-conferences";
import { GamesFilterToolbar } from "./games/GamesFilterToolbar";
import { formatGameStatusLabel } from "./games/game-display";
import {
  buildDayOptions,
  DEFAULT_GAME_SORT_MODE,
  filterGamesByDay,
  filterGamesByCompetition,
  type GameSortMode,
  localDateKey,
  resolveSelectedDay,
  sortGames,
} from "./games/games-view-utils";

export function GamesView({
  token,
  onSignInRequired,
  onManageLeagues,
}: {
  token: string | null;
  onSignInRequired: () => void;
  onManageLeagues: () => void;
}) {
  const queryClient = useQueryClient();
  const { data, isLoading, error: dataError } = useGamesData(token);

  const [dayFilter, setDayFilter] = useState<string | null>(null);
  const [competitionFilter, setCompetitionFilter] = useState<"all" | Competition>("all");
  const [conferenceFilter, setConferenceFilter] = useState<"all" | string>("all");
  const [gameScope, setGameScope] = useState<"all" | "following">("all");
  const [sortMode, setSortMode] = useState<GameSortMode>(DEFAULT_GAME_SORT_MODE);
  const [error, setError] = useState<string | null>(null);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);
  const {
    alertGame,
    gameAlertState,
    alertsBusy,
    openGameAlerts,
    closeGameAlerts,
    updateGameAlertSettings,
    resetGameAlertSettings,
  } = useGameAlertSettings(token, setError);

  const toggleMutation = useMutation({
    mutationFn: async ({ gameId, isFollowed }: { gameId: number; isFollowed: boolean }) => {
      if (!token) return;
      if (isFollowed) {
        await unfollowGame(token, gameId);
      } else {
        await followGame(token, gameId);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.follows(token) });
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  const games = data?.games ?? [];
  const follows = data?.follows;
  const teams = data?.teams ?? [];
  const activeCompetitions = data?.competitions ?? [];
  const competitionVisibility = data?.competitionVisibility ?? { hidden_competitions: [] };
  const hiddenCompetitions = useMemo(
    () => new Set<Competition>(competitionVisibility.hidden_competitions),
    [competitionVisibility.hidden_competitions],
  );
  const visibleCompetitions = useMemo(
    () => activeCompetitions.filter(({ competition }) => !hiddenCompetitions.has(competition)),
    [activeCompetitions, hiddenCompetitions],
  );
  const activeCompetitionIds = useMemo(
    () => new Set(activeCompetitions.map(({ competition }) => competition)),
    [activeCompetitions],
  );
  const competitionProfiles = useMemo(
    () => new Map(activeCompetitions.map((profile) => [profile.competition, profile] as const)),
    [activeCompetitions],
  );

  const teamMap = useMemo(() => new Map(teams.map((team: Team) => [team.id, team])), [teams]);
  const conferenceOptions = useMemo(() => fbsConferenceOptions(teams), [teams]);
  const followedGameIds = useMemo(
    () => new Set((follows?.games ?? []).map((game) => game.id)),
    [follows?.games],
  );

  const visibilityFilteredGames = useMemo(
    () =>
      games.filter(
        (game) =>
          activeCompetitionIds.has(game.competition) && !hiddenCompetitions.has(game.competition),
      ),
    [activeCompetitionIds, games, hiddenCompetitions],
  );
  const visibleFollowedGameCount = useMemo(
    () => visibilityFilteredGames.filter((game) => followedGameIds.has(game.id)).length,
    [followedGameIds, visibilityFilteredGames],
  );
  const scopeFilteredGames = useMemo(
    () =>
      gameScope === "following"
        ? visibilityFilteredGames.filter((game) => followedGameIds.has(game.id))
        : visibilityFilteredGames,
    [followedGameIds, gameScope, visibilityFilteredGames],
  );
  const competitionFilteredGames = useMemo(
    () => filterGamesByCompetition(scopeFilteredGames, competitionFilter),
    [scopeFilteredGames, competitionFilter],
  );
  const conferenceFilteredGames = useMemo(() => {
    if (competitionFilter !== "FBS" || conferenceFilter === "all") {
      return competitionFilteredGames;
    }
    return competitionFilteredGames.filter((game) => {
      const homeConference = teamMap.get(game.home_team_id)?.conference;
      const awayConference = teamMap.get(game.away_team_id)?.conference;
      return homeConference === conferenceFilter || awayConference === conferenceFilter;
    });
  }, [competitionFilter, competitionFilteredGames, conferenceFilter, teamMap]);
  const dayOptions = useMemo(
    () => buildDayOptions(conferenceFilteredGames),
    [conferenceFilteredGames],
  );
  const visibleGames = useMemo(
    () => filterGamesByDay(conferenceFilteredGames, dayFilter),
    [conferenceFilteredGames, dayFilter],
  );
  const sortedVisibleGames = useMemo(
    () => sortGames(visibleGames, sortMode),
    [sortMode, visibleGames],
  );
  const selectedDayLabel = useMemo(() => {
    const firstGame = sortedVisibleGames[0];
    if (!firstGame) return "Games";
    return new Date(firstGame.scheduled_start_time).toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
    });
  }, [sortedVisibleGames]);
  useEffect(() => {
    if (!token && gameScope !== "all") setGameScope("all");
  }, [gameScope, token]);

  useEffect(() => {
    if (
      competitionFilter !== "all" &&
      !visibleCompetitions.some((item) => item.competition === competitionFilter)
    ) {
      setCompetitionFilter("all");
    }
  }, [competitionFilter, visibleCompetitions]);

  useEffect(() => {
    if (
      competitionFilter !== "FBS" ||
      (conferenceFilter !== "all" && !conferenceOptions.includes(conferenceFilter))
    ) {
      setConferenceFilter("all");
    }
  }, [competitionFilter, conferenceFilter, conferenceOptions]);

  useEffect(() => {
    const todayKey = localDateKey(new Date(Date.now()).toISOString());
    const nextDay = resolveSelectedDay(dayOptions, dayFilter, todayKey);
    if (nextDay !== dayFilter) setDayFilter(nextDay);
  }, [dayFilter, dayOptions]);

  return (
    <section className="view-stack games-page" aria-label="Games">
      {error || dataError ? (
        <p className="error view-feedback" role="alert">
          {error ?? messageFromUnknown(dataError)}
        </p>
      ) : null}
      {isLoading ? (
        <p className="muted view-feedback" role="status">
          Loading games...
        </p>
      ) : null}

      {!isLoading ? (
        <div className="games-layout">
          <GamesFilterToolbar
            activeCompetitions={visibleCompetitions}
            competitionFilter={competitionFilter}
            onCompetitionFilterChange={setCompetitionFilter}
            dayFilter={dayFilter}
            onDayFilterChange={setDayFilter}
            dayOptions={dayOptions}
            sortMode={sortMode}
            onSortModeChange={setSortMode}
            showScopeFilter={Boolean(token)}
            gameScope={gameScope}
            onGameScopeChange={setGameScope}
            followedGameCount={visibleFollowedGameCount}
            conferenceOptions={conferenceOptions}
            conferenceFilter={conferenceFilter}
            onConferenceFilterChange={setConferenceFilter}
          />

          <section className="games-feed-scroll" aria-label="Games feed">
            {sortedVisibleGames.length > 0 ? (
              <div className="games-day-list">
                <section className="games-day-board surface" aria-labelledby="games-day-heading">
                  <div className="games-day-header surface-header">
                    <h2 id="games-day-heading">{selectedDayLabel}</h2>
                    <span>
                      {sortedVisibleGames.length}{" "}
                      {sortedVisibleGames.length === 1 ? "game" : "games"}
                    </span>
                  </div>
                  <div
                    className={`games-day-grid last-row-${sortedVisibleGames.length % 3 || 3}`}
                    role="list"
                    aria-label={`${selectedDayLabel} games`}
                  >
                    {sortedVisibleGames.map((game) => {
                      const home = teamMap.get(game.home_team_id);
                      const away = teamMap.get(game.away_team_id);
                      const competitionProfile = competitionProfiles.get(game.competition);
                      if (!home || !away || !competitionProfile) return null;
                      const isFollowed = followedGameIds.has(game.id);

                      return (
                        <GameScoreRow
                          key={game.id}
                          game={game}
                          sport={competitionProfile.sport}
                          home={home}
                          away={away}
                          isFollowed={isFollowed}
                          statusLabel={formatGameStatusLabel(game, competitionProfile.sport)}
                          actionsDisabled={toggleMutation.isPending || busyGameId === game.id}
                          onFollow={() => {
                            if (!token) {
                              onSignInRequired();
                              return;
                            }
                            toggleMutation.mutate({ gameId: game.id, isFollowed: false });
                          }}
                          onUnfollow={async () => {
                            setBusyGameId(game.id);
                            try {
                              await toggleMutation.mutateAsync({
                                gameId: game.id,
                                isFollowed: true,
                              });
                            } finally {
                              setBusyGameId(null);
                            }
                          }}
                          onOpenAlertSettings={() => {
                            openGameAlerts(game).catch(() => undefined);
                          }}
                        />
                      );
                    })}
                  </div>
                </section>
              </div>
            ) : (
              <div className="muted view-feedback empty-visibility-state">
                <p>
                  {visibleCompetitions.length === 0
                    ? "No leagues are currently shown."
                    : gameScope === "following"
                      ? "No followed games match this filter."
                      : "No games in this filter."}
                </p>
                {token && visibleCompetitions.length === 0 ? (
                  <button className="btn" type="button" onClick={onManageLeagues}>
                    Choose leagues
                  </button>
                ) : null}
              </div>
            )}
          </section>
        </div>
      ) : null}

      <GameAlertSettingsModal
        isOpen={Boolean(alertGame)}
        matchupLabel={`${teamMap.get(alertGame?.away_team_id ?? -1)?.abbreviation ?? "AWAY"} @ ${teamMap.get(alertGame?.home_team_id ?? -1)?.abbreviation ?? "HOME"}`}
        alertsBusy={alertsBusy}
        gameAlertState={gameAlertState}
        onClose={closeGameAlerts}
        onUpdateGameAlertSettings={updateGameAlertSettings}
        onResetGameAlertSettings={resetGameAlertSettings}
      />
    </section>
  );
}
