import { useEffect, useMemo, useState } from "react";

import {
  listAlertHistory,
  listAlertPreferences,
  updateAlertPreference,
  type AlertPreference,
  type AlertPreferenceGroup,
  type AlertHistoryItem,
} from "../../../shared/api";
import { PREFERENCE_LABELS, deliveryStatusClass, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";

const ALERT_TYPES_BY_LEAGUE: Record<"NBA" | "MLB", string[]> = {
  NBA: ["game_start", "close_game_late", "final_result"],
  MLB: ["game_start", "inning_start", "final_result"],
};

export function AlertsView({ token }: { token: string }) {
  const { setLastSync } = useDashboardShell();

  const [activeLeague, setActiveLeague] = useState<"NBA" | "MLB">("NBA");
  const [busyAlertType, setBusyAlertType] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [preferenceGroups, setPreferenceGroups] = useState<AlertPreferenceGroup[]>([]);
  const [historyItems, setHistoryItems] = useState<AlertHistoryItem[]>([]);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const [preferenceResponse, historyResponse] = await Promise.all([
        listAlertPreferences(token),
        listAlertHistory(token, { sinceHours: 24 * 7, limit: 100 }),
      ]);
      setPreferenceGroups(preferenceResponse);
      setHistoryItems(historyResponse.items);
      const now = new Date();
      setLastSync(now);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch((loadError) => setError(messageFromUnknown(loadError)));
  }, [token]);

  useEffect(() => {
    const id = window.setInterval(() => {
      load().catch((loadError) => setError(messageFromUnknown(loadError)));
    }, 120_000);
    return () => window.clearInterval(id);
  }, [token]);

  useEffect(() => {
    setLastSync(new Date());
  }, [setLastSync]);

  const onToggle = async (preference: AlertPreference) => {
    setError(null);
    setBusyAlertType(`${preference.league}:${preference.alert_type}`);
    try {
      await updateAlertPreference(token, preference.league, preference.alert_type, {
        is_enabled: !preference.is_enabled,
      });
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const onCloseGameSettingChange = async (preference: AlertPreference, nextMargin: number, nextMinutes: number) => {
    setError(null);
    setBusyAlertType(`${preference.league}:${preference.alert_type}`);
    try {
      await updateAlertPreference(token, preference.league as "NBA" | "MLB", preference.alert_type, {
        is_enabled: preference.is_enabled,
        close_game_margin_threshold: nextMargin,
        close_game_time_threshold_seconds: nextMinutes * 60,
      });
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const onInningStartSettingChange = async (preference: AlertPreference, nextInning: number) => {
    setError(null);
    setBusyAlertType(`${preference.league}:${preference.alert_type}`);
    try {
      await updateAlertPreference(token, preference.league as "NBA" | "MLB", preference.alert_type, {
        is_enabled: preference.is_enabled,
        inning_start_threshold: nextInning,
      });
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const activeGroup = useMemo(() => {
    const raw = preferenceGroups.find((group) => group.league === activeLeague) ?? null;
    if (!raw) return null;
    const allowed = new Set(ALERT_TYPES_BY_LEAGUE[activeLeague]);
    return {
      ...raw,
      preferences: raw.preferences.filter((preference) => allowed.has(preference.alert_type)),
    };
  }, [preferenceGroups, activeLeague]);

  return (
    <section className="view-stack alerts-skeleton-page">
      {error ? <p className="error">{error}</p> : null}
      {loading ? <p className="muted">Loading alerts...</p> : null}

      {!loading ? (
        <div className="alerts-layout">
          <section className="panel alerts-rules-panel">
            <div className="section-header section-header-inline alerts-rules-header">
              <div><h3>Alert Rules</h3></div>
              <div className="chip-row">
                <button className={`chip-btn ${activeLeague === "NBA" ? "active" : ""}`.trim()} type="button" onClick={() => setActiveLeague("NBA")}>NBA</button>
                <button className={`chip-btn ${activeLeague === "MLB" ? "active" : ""}`.trim()} type="button" onClick={() => setActiveLeague("MLB")}>MLB</button>
              </div>
            </div>

            {activeGroup ? (
              <ul className="list">
                {activeGroup.preferences.map((preference) => (
                  <li key={`${preference.league}:${preference.alert_type}`} className={`row-card alert-rule-row ${preference.is_enabled ? "" : "alert-rule-disabled"}`.trim()}>
                    <div className="alert-rule-content">
                      <div className="alert-rule-header">
                        <div className="alert-rule-title-wrap"><strong>{PREFERENCE_LABELS[preference.alert_type] ?? preference.alert_type}</strong></div>
                        <button className={`alert-toggle ${preference.is_enabled ? "on" : "off"}`} type="button" role="switch" aria-checked={preference.is_enabled} disabled={busyAlertType === `${preference.league}:${preference.alert_type}`} onClick={() => onToggle(preference)}><span className="alert-toggle-track"><span className="alert-toggle-thumb" /></span></button>
                      </div>
                      {preference.alert_type === "close_game_late" && preference.is_enabled ? (
                        <div className="alert-rule-controls">
                          <label>Margin<select className="alert-rule-select" value={preference.close_game_margin_threshold ?? 5} onChange={(event) => { const nextMargin = Number(event.target.value); onCloseGameSettingChange(preference, nextMargin, Math.max(1, Math.round((preference.close_game_time_threshold_seconds ?? 120) / 60))).catch((requestError) => setError(messageFromUnknown(requestError))); }} disabled={busyAlertType === `${preference.league}:${preference.alert_type}`}>{[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
                          <label>Minutes<select className="alert-rule-select" value={Math.max(1, Math.round((preference.close_game_time_threshold_seconds ?? 120) / 60))} onChange={(event) => { const nextMinutes = Number(event.target.value); onCloseGameSettingChange(preference, preference.close_game_margin_threshold ?? 5, nextMinutes).catch((requestError) => setError(messageFromUnknown(requestError))); }} disabled={busyAlertType === `${preference.league}:${preference.alert_type}`}>{[1, 2, 3, 4, 5, 10].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
                        </div>
                      ) : null}
                      {preference.alert_type === "inning_start" && preference.is_enabled ? (
                        <div className="alert-rule-controls">
                          <label>Inning
                            <select
                              className="alert-rule-select"
                              value={preference.inning_start_threshold ?? 7}
                              onChange={(event) => {
                                onInningStartSettingChange(preference, Number(event.target.value)).catch((requestError) =>
                                  setError(messageFromUnknown(requestError)),
                                );
                              }}
                              disabled={busyAlertType === `${preference.league}:${preference.alert_type}`}
                            >
                              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((value) => <option key={value} value={value}>{value}</option>)}
                            </select>
                          </label>
                        </div>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">No rules for this league.</p>}
          </section>

          <section className="panel alerts-history-panel">
            <div className="section-header">
              <h3>Alert History</h3>
            </div>
            {historyItems.length === 0 ? <p className="muted">No alert history yet.</p> : null}
            <ul className="list">
              {historyItems.map((item) => (
                <li key={item.id} className="row-card">
                  <span className="alert-history-row-main alerts-history-simple-row">
                    <span>{new Date(item.sent_at).toLocaleString()}</span>
                    <span><strong>{item.away_team_abbreviation}</strong> @ <strong>{item.home_team_abbreviation}</strong></span>
                    <span>{PREFERENCE_LABELS[item.alert_type] ?? item.alert_type}</span>
                  </span>
                  <span className={`chip ${deliveryStatusClass(item.delivery_status)}`}>{item.delivery_status}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}
    </section>
  );
}
