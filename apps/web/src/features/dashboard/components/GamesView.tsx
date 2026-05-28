import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { followGame, type Team, unfollowGame } from "../../../shared/api";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { formatSyncAge } from "../utils/telemetry-format";
import { useGamesData } from "../hooks/useGamesData";
import { useGameAlertSettings } from "../hooks/useGameAlertSettings";
import { GameAlertSettingsModal } from "./GameAlertSettingsModal";
import { GameRowCard } from "./GameRowCard";
import { useDashboardShell } from "./dashboard-shell-context";
import { GamesFiltersPanel } from "./games/GamesFiltersPanel";
import {
  buildDayOptions,
  buildSyncRows,
  filterGamesByDay,
  filterGamesByLeague,
  gameStatusLabel,
  groupGamesByDay,
  latestIngestAtFromGames,
  localDateKey,
  sortGamesByStart,
} from "./games/games-view-utils";

export function GamesView({ token }: { token: string }) {
  const { setLastSync, setHeaderSyncItems } = useDashboardShell();
  const queryClient = useQueryClient();
  const { data, isLoading } = useGamesData(token);

  const [dayFilter, setDayFilter] = useState<"all" | string>("all");
  const [leagueFilter, setLeagueFilter] = useState<"all" | "NBA" | "MLB">("all");
  const [error, setError] = useState<string | null>(null);
  const [busyGameId, setBusyGameId] = useState<number | null>(null);
  const { alertGame, gameAlertState, alertsBusy, openGameAlerts, closeGameAlerts, applyAlertOverride, clearAlertOverride } =
    useGameAlertSettings(token, setError);

  const toggleMutation = useMutation({
    mutationFn: async ({ gameId, isFollowed }: { gameId: number; isFollowed: boolean }) => {
      if (isFollowed) {
        await unfollowGame(token, gameId);
      } else {
        await followGame(token, gameId);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["games-page", token] });
      setLastSync(new Date());
    },
    onError: (mutationError) => setError(messageFromUnknown(mutationError)),
  });

  const games = data?.games ?? [];
  const follows = data?.follows;
  const teams = data?.teams ?? [];

  const teamMap = useMemo(() => new Map(teams.map((team: Team) => [team.id, team])), [teams]);
  const followedGameIds = useMemo(() => new Set((follows?.games ?? []).map((game) => game.id)), [follows?.games]);

  const sortedGames = useMemo(() => sortGamesByStart(games), [games]);
  const leagueFilteredGames = useMemo(() => filterGamesByLeague(sortedGames, leagueFilter), [sortedGames, leagueFilter]);
  const dayOptions = useMemo(() => buildDayOptions(leagueFilteredGames), [leagueFilteredGames]);
  const visibleGames = useMemo(() => filterGamesByDay(leagueFilteredGames, dayFilter), [leagueFilteredGames, dayFilter]);
  const groupedVisibleGames = useMemo(() => groupGamesByDay(visibleGames), [visibleGames]);
  const syncRows = useMemo(() => buildSyncRows(games), [games]);

  useEffect(() => {
    setHeaderSyncItems(
      syncRows.map((row) => ({
        key: row.key,
        label: row.label.replace("Live ", "").replace("(NBA)", "NBA").replace("(MLB)", "MLB"),
        value: formatSyncAge(row.lastAt),
        tone: row.tone,
      })),
    );
    return () => setHeaderSyncItems(null);
  }, [setHeaderSyncItems, syncRows]);

  useEffect(() => {
    setLastSync(latestIngestAtFromGames(games));
  }, [games, setLastSync]);

  useEffect(() => {
    if (dayFilter !== "all" && !dayOptions.some((day) => day.key === dayFilter)) {
      setDayFilter("all");
    }
  }, [dayFilter, dayOptions]);

  useEffect(() => {
    if (dayFilter !== "all") return;
    if (dayOptions.length === 0) return;
    const todayKey = localDateKey(new Date().toISOString());
    const todayOption = dayOptions.find((day) => day.key === todayKey);
    if (todayOption) {
      setDayFilter(todayOption.key);
    }
  }, [dayFilter, dayOptions]);

  return (
    <section className="view-stack games-page">
      <section className="panel games-panel">
        {error ? <p className="error">{error}</p> : null}
        {isLoading ? <p className="muted">Loading games...</p> : null}

        {!isLoading ? (
          <div className="games-feed-grid">
            <GamesFiltersPanel
              leagueFilter={leagueFilter}
              onLeagueFilterChange={setLeagueFilter}
              dayFilter={dayFilter}
              onDayFilterChange={setDayFilter}
              isLoading={isLoading}
              totalLeagueGames={leagueFilteredGames.length}
              dayOptions={dayOptions}
            />

            <div className="data-table-wrap">
              <div className="games-list" role="list" aria-label="Games feed">
                {groupedVisibleGames.map((group) => (
                  <section key={group.label} className="games-day-group">
                    <div className="games-group-row-inner"><strong>{group.label}</strong><span className="muted">{group.items.length} games</span></div>
                    <div className="games-cards">
                      {group.items.map((game) => {
                        const home = teamMap.get(game.home_team_id);
                        const away = teamMap.get(game.away_team_id);
                        if (!home || !away) return null;
                        const isFollowed = followedGameIds.has(game.id);

                        return (
                          <GameRowCard
                            key={game.id}
                            game={game}
                            home={home}
                            away={away}
                            isFollowed={isFollowed}
                            statusLabel={gameStatusLabel(game)}
                            actionsDisabled={toggleMutation.isPending || busyGameId === game.id}
                            onFollow={() => toggleMutation.mutate({ gameId: game.id, isFollowed: false })}
                            onUnfollow={async () => {
                              setBusyGameId(game.id);
                              try {
                                await toggleMutation.mutateAsync({ gameId: game.id, isFollowed: true });
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

        {!isLoading && visibleGames.length === 0 ? <p className="muted">No games in this filter.</p> : null}
      </section>

      <GameAlertSettingsModal
        isOpen={Boolean(alertGame)}
        matchupLabel={`${teamMap.get(alertGame?.away_team_id ?? -1)?.abbreviation ?? "AWAY"} @ ${teamMap.get(alertGame?.home_team_id ?? -1)?.abbreviation ?? "HOME"}`}
        alertsBusy={alertsBusy}
        gameAlertState={gameAlertState}
        onClose={closeGameAlerts}
        onApplyAlertOverride={applyAlertOverride}
        onClearAlertOverride={clearAlertOverride}
      />
    </section>
  );
}
