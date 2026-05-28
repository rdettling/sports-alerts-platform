import { PREFERENCE_LABELS } from "../../../shared/lib/dashboard-ui";
import { type GameAlertPreferences } from "../../../shared/api";
import { AlertRuleCard } from "./alerts/AlertRuleCard";
import { buildGameRuleOverridePayload, getGameFieldValue, ruleFieldsFor } from "./alerts/alert-rule-config";

type GameAlertSettingsModalProps = {
  isOpen: boolean;
  matchupLabel: string;
  alertsBusy: boolean;
  gameAlertState: GameAlertPreferences | null;
  onClose: () => void;
  onApplyAlertOverride: (
    gameId: number,
    alertType: string,
    payload: {
      is_enabled_override?: boolean | null;
      close_game_margin_threshold_override?: number | null;
      close_game_time_threshold_seconds_override?: number | null;
      inning_start_threshold_override?: number | null;
    },
  ) => Promise<void>;
};

export function GameAlertSettingsModal({
  isOpen,
  matchupLabel,
  alertsBusy,
  gameAlertState,
  onClose,
  onApplyAlertOverride,
}: GameAlertSettingsModalProps) {
  if (!isOpen) return null;

  return (
    <div className="overlay-sheet" role="dialog" aria-modal="true">
      <section className="overlay-card game-alert-modal">
        <header className="overlay-card-header">
          <div className="game-alert-modal-title">
            <h4>Game Alert Settings</h4>
            <p className="muted game-alert-matchup">{matchupLabel}</p>
          </div>
          <button className="btn btn-secondary" type="button" onClick={onClose}>
            Close
          </button>
        </header>
        {alertsBusy && !gameAlertState ? <p className="muted">Loading alert settings...</p> : null}
        {gameAlertState ? (
          <ul className="list game-alert-list">
            {gameAlertState.items.map((item) => {
              const fields = ruleFieldsFor(item.alert_type, item.is_enabled);
              const inlineField = fields.length === 1 ? fields[0] : null;
              return (
                <AlertRuleCard
                  key={item.alert_type}
                  title={PREFERENCE_LABELS[item.alert_type] ?? item.alert_type}
                  cardClassName="following-alert-rule-row game-alert-row"
                  headerClassName="following-alert-rule-header"
                  controlsClassName="following-alert-rule-controls"
                  endSlot={
                    <div className="alert-rule-header-end">
                      {inlineField ? (
                        <label className="alert-inline-field">{inlineField.label}
                          <select
                            value={getGameFieldValue(item, inlineField)}
                            disabled={alertsBusy}
                            onChange={(event) => {
                              onApplyAlertOverride(
                                gameAlertState.game_id,
                                item.alert_type,
                                buildGameRuleOverridePayload(item, { fieldKey: inlineField.key, fieldValue: Number(event.target.value) }),
                              ).catch(() => undefined);
                            }}
                          >
                            {inlineField.options.map((value) => <option key={value} value={value}>{value}</option>)}
                          </select>
                        </label>
                      ) : null}
                      <button
                        className={`alert-toggle ${item.is_enabled ? "on" : "off"}`}
                        type="button"
                        role="switch"
                        aria-checked={item.is_enabled}
                        disabled={alertsBusy}
                        onClick={() => {
                          onApplyAlertOverride(
                            gameAlertState.game_id,
                            item.alert_type,
                            buildGameRuleOverridePayload(item, { is_enabled_override: !item.is_enabled }),
                          ).catch(() => undefined);
                        }}
                      >
                        <span className="alert-toggle-track"><span className="alert-toggle-thumb" /></span>
                      </button>
                    </div>
                  }
                  controls={
                    <>
                      {fields.filter((field) => field !== inlineField).map((field) => (
                        <label key={field.key}>{field.label}
                          <select
                            value={getGameFieldValue(item, field)}
                            disabled={alertsBusy}
                            onChange={(event) => {
                              onApplyAlertOverride(
                                gameAlertState.game_id,
                                item.alert_type,
                                buildGameRuleOverridePayload(item, { fieldKey: field.key, fieldValue: Number(event.target.value) }),
                              ).catch(() => undefined);
                            }}
                          >
                            {field.options.map((value) => <option key={value} value={value}>{value}</option>)}
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
