import { useCallback, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { subscribeToGameUpdates, type Game } from "../../../shared/api";
import {
  dashboardQueryKeys,
  gamesFallbackInterval,
  LIVE_GAME_FALLBACK_INTERVAL_MS,
  MIN_GAME_REFRESH_INTERVAL_MS,
} from "./dashboard-query-options";

type UseGameRefreshOptions = {
  games: Game[] | undefined;
  dataUpdatedAt: number;
  isFetching: boolean;
};

export function useGameRefresh({ games, dataUpdatedAt, isFetching }: UseGameRefreshOptions) {
  const queryClient = useQueryClient();
  const pendingRef = useRef(false);
  const isFetchingRef = useRef(isFetching);
  const lastRefreshAtRef = useRef(dataUpdatedAt);
  const refreshTimerRef = useRef<number | null>(null);
  const refreshDueAtRef = useRef<number | null>(null);

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current !== null) {
      window.clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
      refreshDueAtRef.current = null;
    }
  }, []);

  const schedulePendingRefresh = useCallback(() => {
    pendingRef.current = true;
    if (document.visibilityState === "hidden" || isFetchingRef.current) return;

    const now = Date.now();
    const dueAt = Math.max(now, lastRefreshAtRef.current + MIN_GAME_REFRESH_INTERVAL_MS);
    if (refreshDueAtRef.current !== null && refreshDueAtRef.current <= dueAt) return;

    clearRefreshTimer();
    if (dueAt === now) {
      pendingRef.current = false;
      lastRefreshAtRef.current = now;
      void queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.games, exact: true });
      return;
    }

    refreshDueAtRef.current = dueAt;
    refreshTimerRef.current = window.setTimeout(
      () => {
        refreshTimerRef.current = null;
        refreshDueAtRef.current = null;
        if (document.visibilityState === "hidden" || isFetchingRef.current) return;

        pendingRef.current = false;
        lastRefreshAtRef.current = Date.now();
        void queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.games, exact: true });
      },
      Math.max(0, dueAt - now),
    );
  }, [clearRefreshTimer, queryClient]);

  useEffect(() => {
    isFetchingRef.current = isFetching;
    if (dataUpdatedAt > 0) {
      lastRefreshAtRef.current = Math.max(lastRefreshAtRef.current, dataUpdatedAt);
    } else if (isFetching && lastRefreshAtRef.current === 0) {
      lastRefreshAtRef.current = Date.now();
    }
    if (!isFetching && pendingRef.current) schedulePendingRefresh();
  }, [dataUpdatedAt, isFetching, schedulePendingRefresh]);

  useEffect(() => subscribeToGameUpdates(schedulePendingRefresh), [schedulePendingRefresh]);

  useEffect(() => {
    const fallbackInterval = dataUpdatedAt
      ? gamesFallbackInterval(games)
      : LIVE_GAME_FALLBACK_INTERVAL_MS;
    const fallbackTimer = window.setTimeout(schedulePendingRefresh, fallbackInterval);
    return () => window.clearTimeout(fallbackTimer);
  }, [dataUpdatedAt, games, schedulePendingRefresh]);

  useEffect(() => {
    const refreshOnReturn = () => {
      if (document.visibilityState === "hidden") {
        clearRefreshTimer();
        return;
      }
      if (
        pendingRef.current ||
        Date.now() - lastRefreshAtRef.current >= MIN_GAME_REFRESH_INTERVAL_MS
      ) {
        schedulePendingRefresh();
      }
    };

    document.addEventListener("visibilitychange", refreshOnReturn);
    window.addEventListener("focus", refreshOnReturn);
    return () => {
      document.removeEventListener("visibilitychange", refreshOnReturn);
      window.removeEventListener("focus", refreshOnReturn);
    };
  }, [clearRefreshTimer, schedulePendingRefresh]);

  useEffect(() => clearRefreshTimer, [clearRefreshTimer]);
}
