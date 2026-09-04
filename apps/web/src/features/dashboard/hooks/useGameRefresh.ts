import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { subscribeToGameUpdates, type Game } from "../../../shared/api";
import { dashboardQueryKeys, gamesFallbackInterval } from "./dashboard-query-options";

const EVENT_BATCH_MS = 1_000;
const EVENT_REFRESH_SPACING_MS = 2_000;

export function useGameRefresh() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const queryKey = dashboardQueryKeys.games;
    let disposed = false;
    let pageHidden = false;
    let closeStream: (() => void) | null = null;
    let refreshTimer: number | undefined;
    let fallbackTimer: number | undefined;
    let pendingDueAt: number | null = null;
    let fetching = (queryClient.getQueryState(queryKey)?.fetchStatus ?? "idle") !== "idle";
    let lastRequestAt = fetching ? Date.now() : -Infinity;
    let lastReturnAt = -Infinity;

    const isActive = () =>
      !disposed && !pageHidden && document.visibilityState !== "hidden" && navigator.onLine;

    const armRefresh = () => {
      window.clearTimeout(refreshTimer);
      if (!isActive() || fetching || pendingDueAt === null) return;
      refreshTimer = window.setTimeout(
        () => {
          if (!isActive() || fetching) return;
          pendingDueAt = null;
          void queryClient.invalidateQueries({ queryKey, exact: true }, { cancelRefetch: false });
        },
        Math.max(0, pendingDueAt - Date.now()),
      );
    };

    const requestRefresh = (immediate: boolean) => {
      if (!isActive()) return;
      const now = Date.now();
      const dueAt = immediate
        ? now
        : Math.max(now + EVENT_BATCH_MS, lastRequestAt + EVENT_REFRESH_SPACING_MS);
      pendingDueAt = pendingDueAt === null ? dueAt : Math.min(pendingDueAt, dueAt);
      armRefresh();
    };

    const armFallback = () => {
      window.clearTimeout(fallbackTimer);
      if (isActive() && !fetching) {
        fallbackTimer = window.setTimeout(
          () => requestRefresh(true),
          gamesFallbackInterval(queryClient.getQueryData<Game[]>(queryKey)),
        );
      }
    };

    const unsubscribe = queryClient.getQueryCache().subscribe(({ query }) => {
      if (query.queryKey.length !== 1 || query.queryKey[0] !== queryKey[0]) return;
      const wasFetching = fetching;
      fetching = query.state.fetchStatus !== "idle";
      if (fetching && !wasFetching) {
        lastRequestAt = Date.now();
        window.clearTimeout(refreshTimer);
        window.clearTimeout(fallbackTimer);
      }
      if (!fetching && wasFetching) {
        // Failed reads recover on the fallback, not an immediate pending-event loop.
        if (query.state.status === "error") pendingDueAt = null;
        armFallback();
        armRefresh();
      }
    });

    const syncConnection = () => {
      if (!isActive()) {
        closeStream?.();
        closeStream = null;
        lastReturnAt = -Infinity;
        window.clearTimeout(refreshTimer);
        window.clearTimeout(fallbackTimer);
        pendingDueAt = null;
        return;
      }
      if (!closeStream) {
        closeStream = subscribeToGameUpdates(
          () => requestRefresh(false),
          () => requestRefresh(true),
        );
      }
    };

    const refreshOnReturn = () => {
      syncConnection();
      if (!isActive()) return;
      const now = Date.now();
      if (now - lastReturnAt < EVENT_BATCH_MS) return;
      lastReturnAt = now;
      requestRefresh(true);
    };
    const onPageHide = () => {
      pageHidden = true;
      syncConnection();
    };
    const onPageShow = () => {
      pageHidden = false;
      refreshOnReturn();
    };

    syncConnection();
    armFallback();
    document.addEventListener("visibilitychange", refreshOnReturn);
    window.addEventListener("focus", refreshOnReturn);
    window.addEventListener("online", refreshOnReturn);
    window.addEventListener("offline", syncConnection);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);
    return () => {
      disposed = true;
      syncConnection();
      unsubscribe();
      document.removeEventListener("visibilitychange", refreshOnReturn);
      window.removeEventListener("focus", refreshOnReturn);
      window.removeEventListener("online", refreshOnReturn);
      window.removeEventListener("offline", syncConnection);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onPageShow);
    };
  }, [queryClient]);
}
