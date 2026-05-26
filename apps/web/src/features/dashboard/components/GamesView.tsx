import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { followGame, type Game, type Team, unfollowGame } from "../../../shared/api";
import { TeamLogo, formatGameTime, formatMoneyline, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";
import { useGamesData } from "../hooks/useGamesData";

type GameDayGroup = { label: string; items: Game[] };

function localDateKey(dateIso: string): string {
  const value = new Date(dateIso);
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function GamesView({ token }: { token: string }) {
  const { setLastSync } = useDashboardShell();
  const queryClient = useQueryClient();
  const { data, isLoading } = useGamesData(token);

  const [dayFilter, setDayFilter] = useState<"all" | string>("all");
  const [leagueFilter, setLeagueFilter] = useState<"all" | "NBA" | "MLB">("all");
  const [error, setError] = useState<string | null>(null);

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

  const sortedGames = useMemo(
    () => [...games].sort((a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime()),
    [games],
  );

  const gameDateKey = (game: Game): string => localDateKey(game.scheduled_start_time);

  const leagueFilteredGames = useMemo(() => {
    if (leagueFilter === "all") return sortedGames;
    return sortedGames.filter((game) => (game.league || "").toUpperCase() === leagueFilter);
  }, [sortedGames, leagueFilter]);

  const dayOptions = useMemo(() => {
    const map = new Map<string, { key: string; label: string; count: number }>();
    leagueFilteredGames.forEach((game) => {
      const key = gameDateKey(game);
      const label = new Date(game.scheduled_start_time).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
      const current = map.get(key);
      if (current) current.count += 1;
      else map.set(key, { key, label, count: 1 });
    });
    return Array.from(map.values());
  }, [leagueFilteredGames]);

  const visibleGames = useMemo(() => {
    if (dayFilter === "all") return leagueFilteredGames;
    return leagueFilteredGames.filter((game) => gameDateKey(game) === dayFilter);
  }, [leagueFilteredGames, dayFilter]);

  const groupedVisibleGames: GameDayGroup[] = useMemo(() => {
    const groups = new Map<string, Game[]>();
    visibleGames.forEach((game) => {
      const label = new Date(game.scheduled_start_time).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
      const current = groups.get(label) ?? [];
      current.push(game);
      groups.set(label, current);
    });
    return Array.from(groups.entries()).map(([label, items]) => ({ label, items }));
  }, [visibleGames]);

  const statusLabel = (game: Game): string => {
    if (game.status === "in_progress" || game.status === "live") {
      return `Live • ${formatGameTime(game)}`;
    }
    if (game.status === "final" || game.is_final) {
      return "Final";
    }
    return new Date(game.scheduled_start_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  };

  useEffect(() => {
    const latestMs = games.reduce((latest, game) => {
      if (!game.last_ingested_at) return latest;
      const ts = new Date(game.last_ingested_at).getTime();
      if (Number.isNaN(ts)) return latest;
      return Math.max(latest, ts);
    }, 0);
    setLastSync(latestMs > 0 ? new Date(latestMs) : null);
  }, [games, setLastSync]);

  useEffect(() => {
    if (dayFilter !== "all" && !dayOptions.some((day) => day.key === dayFilter)) {
      setDayFilter("all");
    }
  }, [dayFilter, dayOptions]);

  return (
    <section className="view-stack games-page">
      <section className="panel games-panel">
        {error ? <p className="error">{error}</p> : null}
        {isLoading ? <p className="muted">Loading games...</p> : null}

        {!isLoading ? (
          <div className="games-feed-grid">
            <aside className="games-day-filter">
              <div className="games-league-filter" role="tablist" aria-label="League filter">
                <button className={`chip-btn ${leagueFilter === "all" ? "active" : ""}`.trim()} onClick={() => setLeagueFilter("all")} disabled={isLoading}>All</button>
                <button className={`chip-btn ${leagueFilter === "NBA" ? "active" : ""}`.trim()} onClick={() => setLeagueFilter("NBA")} disabled={isLoading}>NBA</button>
                <button className={`chip-btn ${leagueFilter === "MLB" ? "active" : ""}`.trim()} onClick={() => setLeagueFilter("MLB")} disabled={isLoading}>MLB</button>
              </div>
              <button className={`games-day-filter-btn ${dayFilter === "all" ? "active" : ""}`.trim()} onClick={() => setDayFilter("all")} disabled={isLoading}>
                <span>All</span>
                <span className="muted">{leagueFilteredGames.length}</span>
              </button>
              {dayOptions.map((day) => (
                <button key={day.key} className={`games-day-filter-btn ${dayFilter === day.key ? "active" : ""}`.trim()} onClick={() => setDayFilter(day.key)} disabled={isLoading}>
                  <span>{day.label}</span>
                  <span className="muted">{day.count}</span>
                </button>
              ))}
            </aside>

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
                        const hasScore = game.away_score !== null && game.home_score !== null;
                        const awayWon = Boolean(hasScore && game.is_final && game.away_score! > game.home_score!);
                        const homeWon = Boolean(hasScore && game.is_final && game.home_score! > game.away_score!);
                        const isLive = game.status === "in_progress" || game.status === "live";
                        const isFinal = game.status === "final" || game.is_final;
                        const showScoreValues = isLive || isFinal;
                        const awayValueText = showScoreValues
                          ? String(game.away_score ?? "—")
                          : game.odds
                            ? formatMoneyline(game.odds.away_moneyline)
                            : "—";
                        const homeValueText = showScoreValues
                          ? String(game.home_score ?? "—")
                          : game.odds
                            ? formatMoneyline(game.odds.home_moneyline)
                            : "—";

                        return (
                          <article key={game.id} className="games-card-row" role="listitem">
                            <div className="games-card-main">
                              <div className="games-matchup-lines">
                                <div className={`games-team-line ${awayWon ? "winner" : ""}`.trim()}>
                                  <div className="games-team-ident"><TeamLogo team={away} size={24} /><strong>{away.abbreviation}</strong></div>
                                </div>
                                <div className={`games-team-line ${homeWon ? "winner" : ""}`.trim()}>
                                  <div className="games-team-ident"><TeamLogo team={home} size={24} /><strong>{home.abbreviation}</strong></div>
                                </div>
                              </div>

                              <div className="games-values-lines">
                                <div className={`games-team-score ${awayWon ? "winner" : ""}`.trim()}>{awayValueText}{awayWon ? <span className="games-winner-tag">W</span> : null}</div>
                                <div className={`games-team-score ${homeWon ? "winner" : ""}`.trim()}>{homeValueText}{homeWon ? <span className="games-winner-tag">W</span> : null}</div>
                              </div>

                              <div className="games-meta-rail">
                                <span className="games-league-pill">{(game.league || "N/A").toUpperCase()}</span>
                                <span className={`games-status-pill ${isLive ? "live" : isFinal ? "final" : "scheduled"}`.trim()}>{statusLabel(game)}</span>
                                <button className={`btn ${isFollowed ? "btn-secondary" : ""} games-action-cell`.trim()} disabled={toggleMutation.isPending} onClick={() => toggleMutation.mutate({ gameId: game.id, isFollowed })}>{isFollowed ? "Following" : "Follow"}</button>
                              </div>
                            </div>
                          </article>
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
    </section>
  );
}
