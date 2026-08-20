import { useEffect } from "react";

import { PREFERENCE_LABELS } from "../../../shared/lib/dashboard-ui";
import { type AlertSettingsUpdate, type GameAlertPreferences } from "../../../shared/api";
import { AlertRuleCard } from "./alerts/AlertRuleCard";
import {
  buildAlertSettingsPayload,
  getRuleFieldValue,
  ruleFieldsFor,
} from "./alerts/alert-rule-config";

type GameAlertSettingsModalProps = {
  isOpen: boolean;
  matchupLabel: string;
  alertsBusy: boolean;
  gameAlertState: GameAlertPreferences | null;
  onClose: () => void;
  onUpdateGameAlertSettings: (
    gameId: number,
    alertType: string,
    payload: AlertSettingsUpdate,
  ) => Promise<void>;
  onResetGameAlertSettings: (gameId: number, alertType: string) => Promise<void>;
};

export function GameAlertSettingsModal({
  isOpen,
  matchupLabel,
  alertsBusy,
  gameAlertState,
  onClose,
  onUpdateGameAlertSettings,
  onResetGameAlertSettings,
}: GameAlertSettingsModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="overlay-sheet game-alert-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="game-alert-title"
      aria-describedby="game-alert-matchup"
    >
      <section className="overlay-card game-alert-modal">
        <header className="overlay-card-header">
          <div className="game-alert-modal-title">
            <h4 id="game-alert-title">Game Alert Settings</h4>
            <p id="game-alert-matchup" className="muted game-alert-matchup">
              {matchupLabel}
            </p>
          </div>
          <button className="btn btn-secondary" type="button" onClick={onClose}>
            Close
          </button>
        </header>
        {alertsBusy && !gameAlertState ? (
          <p className="muted" role="status">
            Loading alert settings...
          </p>
        ) : null}
        {gameAlertState ? (
          <ul className="game-alert-list">
            {gameAlertState.items.map((item) => {
              const fields = ruleFieldsFor(item.alert_type, item.is_enabled);
              const inlineField = fields.length === 1 ? fields[0] : null;
              return (
                <AlertRuleCard
                  key={item.alert_type}
                  title={PREFERENCE_LABELS[item.alert_type] ?? item.alert_type}
                  cardClassName="game-alert-row"
                  headerClassName="game-alert-rule-header"
                  controlsClassName="game-alert-rule-controls"
                  endSlot={
                    <div className="alert-rule-header-end">
                      {!item.uses_sport_defaults ? (
                        <button
                          className="game-alert-reset"
                          type="button"
                          disabled={alertsBusy}
                          onClick={() => {
                            onResetGameAlertSettings(gameAlertState.game_id, item.alert_type).catch(
                              () => undefined,
                            );
                          }}
                        >
                          Use sport settings
                        </button>
                      ) : null}
                      {inlineField ? (
                        <label className="alert-inline-field">
                          {inlineField.label}
                          <select
                            value={getRuleFieldValue(item, inlineField)}
                            disabled={alertsBusy}
                            onChange={(event) => {
                              onUpdateGameAlertSettings(
                                gameAlertState.game_id,
                                item.alert_type,
                                buildAlertSettingsPayload(item, {
                                  fieldKey: inlineField.key,
                                  fieldValue: Number(event.target.value),
                                }),
                              ).catch(() => undefined);
                            }}
                          >
                            {inlineField.options.map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                      ) : null}
                      <button
                        className={`alert-toggle ${item.is_enabled ? "on" : "off"}`}
                        type="button"
                        role="switch"
                        aria-label={`${PREFERENCE_LABELS[item.alert_type] ?? item.alert_type} alerts for this game`}
                        aria-checked={item.is_enabled}
                        disabled={alertsBusy}
                        onClick={() => {
                          onUpdateGameAlertSettings(
                            gameAlertState.game_id,
                            item.alert_type,
                            buildAlertSettingsPayload(item, {
                              is_enabled: !item.is_enabled,
                            }),
                          ).catch(() => undefined);
                        }}
                      >
                        <span className="alert-toggle-label" aria-hidden>
                          {item.is_enabled ? "On" : "Off"}
                        </span>
                        <span className="alert-toggle-track" aria-hidden>
                          <span className="alert-toggle-thumb" />
                        </span>
                      </button>
                    </div>
                  }
                  controls={
                    <>
                      {fields
                        .filter((field) => field !== inlineField)
                        .map((field) => (
                          <label key={field.key}>
                            {field.label}
                            <select
                              value={getRuleFieldValue(item, field)}
                              disabled={alertsBusy}
                              onChange={(event) => {
                                onUpdateGameAlertSettings(
                                  gameAlertState.game_id,
                                  item.alert_type,
                                  buildAlertSettingsPayload(item, {
                                    fieldKey: field.key,
                                    fieldValue: Number(event.target.value),
                                  }),
                                ).catch(() => undefined);
                              }}
                            >
                              {field.options.map((value) => (
                                <option key={value} value={value}>
                                  {value}
                                </option>
                              ))}
                            </select>
                          </label>
                        ))}
                    </>
                  }
                />
              );
            })}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
