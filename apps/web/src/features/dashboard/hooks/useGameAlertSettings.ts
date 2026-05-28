import { useState } from "react";

import {
  clearGameAlertOverride,
  getGameAlertPreferences,
  type Game,
  type GameAlertPreferences,
  updateGameAlertOverride,
} from "../../../shared/api";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";

type AlertOverridePayload = {
  is_enabled_override?: boolean | null;
  close_game_margin_threshold_override?: number | null;
  close_game_time_threshold_seconds_override?: number | null;
  inning_start_threshold_override?: number | null;
};

export function useGameAlertSettings(token: string, setError: (value: string | null) => void) {
  const [alertGame, setAlertGame] = useState<Game | null>(null);
  const [gameAlertState, setGameAlertState] = useState<GameAlertPreferences | null>(null);
  const [alertsBusy, setAlertsBusy] = useState(false);

  const openGameAlerts = async (game: Game) => {
    setError(null);
    setAlertGame(game);
    setAlertsBusy(true);
    try {
      const payload = await getGameAlertPreferences(token, game.id);
      setGameAlertState(payload);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
      setAlertGame(null);
    } finally {
      setAlertsBusy(false);
    }
  };

  const closeGameAlerts = () => {
    setAlertGame(null);
    setGameAlertState(null);
  };

  const applyAlertOverride = async (gameId: number, alertType: string, payload: AlertOverridePayload) => {
    setAlertsBusy(true);
    setError(null);
    try {
      await updateGameAlertOverride(token, gameId, alertType, payload);
      const refreshed = await getGameAlertPreferences(token, gameId);
      setGameAlertState(refreshed);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setAlertsBusy(false);
    }
  };

  const clearAlertOverride = async (gameId: number, alertType: string) => {
    setAlertsBusy(true);
    setError(null);
    try {
      await clearGameAlertOverride(token, gameId, alertType);
      const refreshed = await getGameAlertPreferences(token, gameId);
      setGameAlertState(refreshed);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setAlertsBusy(false);
    }
  };

  return {
    alertGame,
    gameAlertState,
    alertsBusy,
    openGameAlerts,
    closeGameAlerts,
    applyAlertOverride,
    clearAlertOverride,
  };
}
