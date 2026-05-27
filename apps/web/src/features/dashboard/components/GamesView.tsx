import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { followGame, type Game, type Team, unfollowGame } from "../../../shared/api";
import { TeamLogo, formatGameTime, formatMoneyline, leagueLogoUrl, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";
import { useGamesData } from "../hooks/useGamesData";

type GameDayGroup = { label: string; items: Game[] };
type SyncTone = "fresh" | "stale" | "idle";

type SyncRow = {
  key: string;
  label: string;
  cadenceLabel: string;
  lastAt: Date | null;
  detail: string;
  tone: SyncTone;
};

function localDateKey(dateIso: string): string {
  const value = new Date(dateIso);
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatRelativeTime(value: Date | null): string {
  if (!value) return "Never";
  const diffMs = Date.now() - value.getTime();
  if (diffMs < 60_000) return "Just now";
  const mins = Math.round(diffMs / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

function syncTone(lastAt: Date | null, maxStaleMinutes: number, active: boolean): SyncTone {
  if (!lastAt) return "stale";
  if (!active) return "idle";
  const ageMinutes = (Date.now() - lastAt.getTime()) / 60_000;
  return ageMinutes <= maxStaleMinutes ? "fresh" : "stale";
}

export function GamesView({ token }: { token: string }) {
  const { setLastSync, setHeaderSyncItems } = useDashboardShell();
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

  const syncRows = useMemo(() => {
    const byLeague = (league: "NBA" | "MLB") => {
      const leagueGames = games.filter((game) => (game.league || "").toUpperCase() === league);
      const liveCount = leagueGames.filter((game) => game.status === "in_progress" || game.status === "live").length;
      const nextStartMs = leagueGames
        .filter((game) => game.status === "scheduled")
        .map((game) => new Date(game.scheduled_start_time).getTime())
        .filter((ts) => !Number.isNaN(ts))
        .sort((a, b) => a - b)[0];
      const lastMs = leagueGames
        .map((game) => (game.last_ingested_at ? new Date(game.last_ingested_at).getTime() : Number.NaN))
        .filter((ts) => !Number.isNaN(ts))
        .reduce((max, ts) => Math.max(max, ts), 0);
      const lastAt = lastMs > 0 ? new Date(lastMs) : null;
      return { liveCount, nextStartMs, lastAt };
    };

    const nba = byLeague("NBA");
    const mlb = byLeague("MLB");
    const allLastMs = games
      .map((game) => (game.last_ingested_at ? new Date(game.last_ingested_at).getTime() : Number.NaN))
      .filter((ts) => !Number.isNaN(ts))
      .reduce((max, ts) => Math.max(max, ts), 0);
    const catalogLastAt = allLastMs > 0 ? new Date(allLastMs) : null;

    const leagueRow = (label: string, cadenceLabel: string, info: { liveCount: number; nextStartMs?: number; lastAt: Date | null }, staleAfterMinutes: number): SyncRow => {
      const active = info.liveCount > 0;
      const detail = active
        ? `${info.liveCount} live`
        : info.nextStartMs
          ? `Next ${new Date(info.nextStartMs).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`
          : "No upcoming";
      return {
        key: label,
        label,
        cadenceLabel,
        lastAt: info.lastAt,
        detail,
        tone: syncTone(info.lastAt, staleAfterMinutes, active),
      };
    };

    return [
      {
        key: "catalog",
        label: "Catalog",
        cadenceLabel: "12h cadence",
        lastAt: catalogLastAt,
        detail: "Schedule + odds snapshot",
        tone: syncTone(catalogLastAt, 12 * 60 + 30, true),
      },
      leagueRow("Live (NBA)", "2m cadence", nba, 4),
      leagueRow("Live (MLB)", "5m cadence", mlb, 10),
    ] satisfies SyncRow[];
  }, [games]);

  useEffect(() => {
    setHeaderSyncItems(
      syncRows.map((row) => ({
        key: row.key,
        label: row.label.replace("Live ", "").replace("(NBA)", "NBA").replace("(MLB)", "MLB"),
        value: formatRelativeTime(row.lastAt),
        tone: row.tone,
      })),
    );
    return () => setHeaderSyncItems(null);
  }, [setHeaderSyncItems, syncRows]);

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
                              <div className="games-lines">
                                <div className={`games-team-row ${awayWon ? "winner" : ""}`.trim()}>
                                  <div className="games-team-ident"><TeamLogo team={away} size={24} /><strong>{away.abbreviation}</strong></div>
                                  <div className="games-team-score">{awayValueText}</div>
                                </div>
                                <div className={`games-team-row ${homeWon ? "winner" : ""}`.trim()}>
                                  <div className="games-team-ident"><TeamLogo team={home} size={24} /><strong>{home.abbreviation}</strong></div>
                                  <div className="games-team-score">{homeValueText}</div>
                                </div>
                              </div>

                              <div className="games-meta-rail">
                                {leagueLogoUrl(game.league) ? (
                                  <span className="games-league-logo-wrap" aria-label={`${(game.league || "N/A").toUpperCase()} league`}>
                                    <img
                                      src={leagueLogoUrl(game.league) ?? ""}
                                      alt={`${(game.league || "N/A").toUpperCase()} logo`}
                                      className={`games-league-logo league-${(game.league || "").toLowerCase()}`.trim()}
                                    />
                                  </span>
                                ) : (
                                  <span className="games-league-logo-fallback">{(game.league || "N/A").toUpperCase()}</span>
                                )}
                                {!isFinal ? <span className={`games-status-pill ${isLive ? "live" : "scheduled"}`.trim()}>{statusLabel(game)}</span> : null}
                                {isFinal ? (
                                  <span className="games-outcome-pill final">Final</span>
                                ) : (
                                  <button className={`btn ${isFollowed ? "btn-secondary" : ""} games-action-cell`.trim()} disabled={toggleMutation.isPending} onClick={() => toggleMutation.mutate({ gameId: game.id, isFollowed })}>{isFollowed ? "Following" : "Follow"}</button>
                                )}
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
