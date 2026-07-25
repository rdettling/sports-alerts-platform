import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { followGame, type League, type Team, unfollowGame } from "../../../shared/api";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { useGamesData } from "../hooks/useGamesData";
import { useGameAlertSettings } from "../hooks/useGameAlertSettings";
import { GameAlertSettingsModal } from "./GameAlertSettingsModal";
import { GameRowCard } from "./GameRowCard";
import { GamesFilterToolbar } from "./games/GamesFilterToolbar";
import {
  buildDayOptions,
  filterGamesByDay,
  filterGamesByLeague,
  gameStatusLabel,
  groupGamesByDay,
  localDateKey,
  sortGamesByStart,
} from "./games/games-view-utils";

export function GamesView({
  token,
  onSignInRequired,
}: {
  token: string | null;
  onSignInRequired: () => void;
}) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useGamesData(token);

  const [dayFilter, setDayFilter] = useState<"all" | string>("all");
  const [leagueFilter, setLeagueFilter] = useState<"all" | League>("all");
  const [gameScope, setGameScope] = useState<"all" | "following">("all");
  const [error, setError] = useState<string | null>(null);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);
  const hasAutoSelectedInitialDay = useRef(false);
  const {
    alertGame,
    gameAlertState,
    alertsBusy,
    openGameAlerts,
    closeGameAlerts,
    applyAlertOverride,
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
      await queryClient.invalidateQueries({ queryKey: ["games-page", token] });
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  const games = data?.games ?? [];
  const follows = data?.follows;
  const teams = data?.teams ?? [];
  const activeLeagues = data?.leagues ?? [];
  const leagueProfiles = useMemo(
    () => new Map(activeLeagues.map((profile) => [profile.league, profile] as const)),
    [activeLeagues],
  );

  const teamMap = useMemo(() => new Map(teams.map((team: Team) => [team.id, team])), [teams]);
  const followedGameIds = useMemo(
    () => new Set((follows?.games ?? []).map((game) => game.id)),
    [follows?.games],
  );

  const sortedGames = useMemo(() => sortGamesByStart(games), [games]);
  const scopeFilteredGames = useMemo(
    () =>
      gameScope === "following"
        ? sortedGames.filter((game) => followedGameIds.has(game.id))
        : sortedGames,
    [followedGameIds, gameScope, sortedGames],
  );
  const leagueFilteredGames = useMemo(
    () => filterGamesByLeague(scopeFilteredGames, leagueFilter),
    [scopeFilteredGames, leagueFilter],
  );
  const dayOptions = useMemo(() => buildDayOptions(leagueFilteredGames), [leagueFilteredGames]);
  const visibleGames = useMemo(
    () => filterGamesByDay(leagueFilteredGames, dayFilter),
    [leagueFilteredGames, dayFilter],
  );
  const groupedVisibleGames = useMemo(() => groupGamesByDay(visibleGames), [visibleGames]);
  useEffect(() => {
    if (!token && gameScope !== "all") setGameScope("all");
  }, [gameScope, token]);

  useEffect(() => {
    if (leagueFilter !== "all" && !activeLeagues.some((item) => item.league === leagueFilter)) {
      setLeagueFilter("all");
    }
  }, [activeLeagues, leagueFilter]);

  useEffect(() => {
    if (dayFilter !== "all" && !dayOptions.some((day) => day.key === dayFilter)) {
      setDayFilter("all");
    }
  }, [dayFilter, dayOptions]);

  useEffect(() => {
    if (hasAutoSelectedInitialDay.current) return;
    if (dayFilter !== "all") return;
    if (dayOptions.length === 0) return;
    const todayKey = localDateKey(new Date(Date.now()).toISOString());
    const todayOption = dayOptions.find((day) => day.key === todayKey);
    if (todayOption) {
      hasAutoSelectedInitialDay.current = true;
      setDayFilter(todayOption.key);
    }
  }, [dayFilter, dayOptions]);

  return (
    <section className="view-stack games-page">
      <p className="games-page-intro">
        Live scores and customizable email and push alerts for NBA, WNBA, MLB, MLS, and World Cup
        games.
      </p>
      <section className="panel games-panel">
        {error ? <p className="error">{error}</p> : null}
        {isLoading ? <p className="muted">Loading games...</p> : null}

        {!isLoading ? (
          <div className="games-feed-grid">
            <GamesFilterToolbar
              activeLeagues={activeLeagues}
              leagueFilter={leagueFilter}
              onLeagueFilterChange={setLeagueFilter}
              dayFilter={dayFilter}
              onDayFilterChange={setDayFilter}
              totalLeagueGames={leagueFilteredGames.length}
              dayOptions={dayOptions}
              showScopeFilter={Boolean(token)}
              gameScope={gameScope}
              onGameScopeChange={setGameScope}
              followedGameCount={followedGameIds.size}
            />

            <div className="games-feed-scroll">
              <div className="games-list" role="list" aria-label="Games feed">
                {groupedVisibleGames.map((group) => (
                  <section key={group.label} className="games-day-group">
                    <div className="games-group-row-inner">
                      <strong>{group.label}</strong>
                      <span className="muted">{group.items.length} games</span>
                    </div>
                    <div className="games-cards">
                      {group.items.map((game) => {
                        const home = teamMap.get(game.home_team_id);
                        const away = teamMap.get(game.away_team_id);
                        const leagueProfile = leagueProfiles.get(game.league);
                        if (!home || !away || !leagueProfile) return null;
                        const isFollowed = followedGameIds.has(game.id);

                        return (
                          <GameRowCard
                            key={game.id}
                            game={game}
                            sport={leagueProfile.sport}
                            home={home}
                            away={away}
                            isFollowed={isFollowed}
                            statusLabel={gameStatusLabel(game, leagueProfile.sport)}
                            showContextLabel
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
                ))}
              </div>
            </div>
          </div>
        ) : null}

        {!isLoading && visibleGames.length === 0 ? (
          <p className="muted">
            {gameScope === "following"
              ? "No followed games match this filter."
              : "No games in this filter."}
          </p>
        ) : null}
      </section>

      <GameAlertSettingsModal
        isOpen={Boolean(alertGame)}
        matchupLabel={`${teamMap.get(alertGame?.away_team_id ?? -1)?.abbreviation ?? "AWAY"} @ ${teamMap.get(alertGame?.home_team_id ?? -1)?.abbreviation ?? "HOME"}`}
        alertsBusy={alertsBusy}
        gameAlertState={gameAlertState}
        onClose={closeGameAlerts}
        onApplyAlertOverride={applyAlertOverride}
      />
    </section>
  );
}
