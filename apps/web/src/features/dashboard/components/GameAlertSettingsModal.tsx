import { PREFERENCE_LABELS } from "../../../shared/lib/dashboard-ui";
import { type GameAlertPreferences } from "../../../shared/api";

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
  onClearAlertOverride: (gameId: number, alertType: string) => Promise<void>;
};

export function GameAlertSettingsModal({
  isOpen,
  matchupLabel,
  alertsBusy,
  gameAlertState,
  onClose,
  onApplyAlertOverride,
  onClearAlertOverride,
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
            {gameAlertState.items.map((item) => (
              <li key={item.alert_type} className="row-card following-alert-rule-row game-alert-row">
                <div className="following-alert-rule-header">
                  <strong className="game-alert-rule-name">{PREFERENCE_LABELS[item.alert_type] ?? item.alert_type}</strong>
                  <label className="following-alert-default-toggle">
                    <input
                      type="checkbox"
                      checked={item.use_league_default}
                      disabled={alertsBusy}
                      onChange={(event) => {
                        if (event.target.checked) {
                          onClearAlertOverride(gameAlertState.game_id, item.alert_type).catch(() => undefined);
                        } else {
                          onApplyAlertOverride(gameAlertState.game_id, item.alert_type, {
                            is_enabled_override: item.is_enabled,
                            close_game_margin_threshold_override: item.alert_type === "close_game_late" ? item.close_game_margin_threshold : null,
                            close_game_time_threshold_seconds_override: item.alert_type === "close_game_late" ? item.close_game_time_threshold_seconds : null,
                            inning_start_threshold_override: item.alert_type === "inning_start" ? item.inning_start_threshold : null,
                          }).catch(() => undefined);
                        }
                      }}
                    />
                    Use league default
                  </label>
                </div>
                <div className="following-alert-rule-controls">
                  <label>Enabled
                    <select
                      value={item.is_enabled ? "on" : "off"}
                      disabled={alertsBusy || item.use_league_default}
                      onChange={(event) => {
                        onApplyAlertOverride(gameAlertState.game_id, item.alert_type, {
                          is_enabled_override: event.target.value === "on",
                          close_game_margin_threshold_override: item.override?.close_game_margin_threshold_override ?? null,
                          close_game_time_threshold_seconds_override: item.override?.close_game_time_threshold_seconds_override ?? null,
                          inning_start_threshold_override: item.override?.inning_start_threshold_override ?? null,
                        }).catch(() => undefined);
                      }}
                    >
                      <option value="on">On</option>
                      <option value="off">Off</option>
                    </select>
                  </label>
                  {item.alert_type === "close_game_late" ? (
                    <>
                      <label>Margin
                        <select
                          value={item.close_game_margin_threshold ?? 5}
                          disabled={alertsBusy || item.use_league_default}
                          onChange={(event) => {
                            onApplyAlertOverride(gameAlertState.game_id, item.alert_type, {
                              is_enabled_override: item.override?.is_enabled_override ?? item.is_enabled,
                              close_game_margin_threshold_override: Number(event.target.value),
                              close_game_time_threshold_seconds_override: item.close_game_time_threshold_seconds ?? 120,
                            }).catch(() => undefined);
                          }}
                        >
                          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => <option key={value} value={value}>{value}</option>)}
                        </select>
                      </label>
                      <label>Seconds
                        <select
                          value={item.close_game_time_threshold_seconds ?? 120}
                          disabled={alertsBusy || item.use_league_default}
                          onChange={(event) => {
                            onApplyAlertOverride(gameAlertState.game_id, item.alert_type, {
                              is_enabled_override: item.override?.is_enabled_override ?? item.is_enabled,
                              close_game_margin_threshold_override: item.close_game_margin_threshold ?? 5,
                              close_game_time_threshold_seconds_override: Number(event.target.value),
                            }).catch(() => undefined);
                          }}
                        >
                          {[30, 60, 90, 120, 180, 300].map((value) => <option key={value} value={value}>{value}</option>)}
                        </select>
                      </label>
                    </>
                  ) : null}
                  {item.alert_type === "inning_start" ? (
                    <label>Inning
                      <select
                        value={item.inning_start_threshold ?? 7}
                        disabled={alertsBusy || item.use_league_default}
                        onChange={(event) => {
                          onApplyAlertOverride(gameAlertState.game_id, item.alert_type, {
                            is_enabled_override: item.override?.is_enabled_override ?? item.is_enabled,
                            inning_start_threshold_override: Number(event.target.value),
                            close_game_margin_threshold_override: null,
                            close_game_time_threshold_seconds_override: null,
                          }).catch(() => undefined);
                        }}
                      >
                        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((value) => <option key={value} value={value}>{value}</option>)}
                      </select>
                    </label>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
