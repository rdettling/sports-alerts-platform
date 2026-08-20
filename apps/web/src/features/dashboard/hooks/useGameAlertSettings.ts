import { useState } from "react";

import {
  getGameAlertPreferences,
  resetGameAlertSettings as requestGameAlertReset,
  type AlertSettingsUpdate,
  type Game,
  type GameAlertPreferenceItem,
  type GameAlertPreferences,
  updateGameAlertSettings as requestGameAlertUpdate,
} from "../../../shared/api";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";

export function useGameAlertSettings(
  token: string | null,
  setError: (value: string | null) => void,
) {
  const [alertGame, setAlertGame] = useState<Game | null>(null);
  const [gameAlertState, setGameAlertState] = useState<GameAlertPreferences | null>(null);
  const [alertsBusy, setAlertsBusy] = useState(false);

  const openGameAlerts = async (game: Game) => {
    if (!token) return;
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

  const replaceGameAlertItem = (gameId: number, updated: GameAlertPreferenceItem) => {
    setGameAlertState((current) =>
      current?.game_id === gameId
        ? {
            ...current,
            items: current.items.map((item) =>
              item.alert_type === updated.alert_type ? updated : item,
            ),
          }
        : current,
    );
  };

  const updateGameAlertSettings = async (
    gameId: number,
    alertType: string,
    payload: AlertSettingsUpdate,
  ) => {
    if (!token) return;
    setAlertsBusy(true);
    setError(null);
    try {
      const updated = await requestGameAlertUpdate(token, gameId, alertType, payload);
      replaceGameAlertItem(gameId, updated);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setAlertsBusy(false);
    }
  };

  const resetGameAlertSettings = async (gameId: number, alertType: string) => {
    if (!token) return;
    setAlertsBusy(true);
    setError(null);
    try {
      const updated = await requestGameAlertReset(token, gameId, alertType);
      replaceGameAlertItem(gameId, updated);
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
    updateGameAlertSettings,
    resetGameAlertSettings,
  };
}
