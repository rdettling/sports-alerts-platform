import { useEffect, useMemo, useState } from "react";

import {
  listAlertHistory,
  listAlertPreferences,
  listLeagues,
  updateAlertPreference,
  type League,
  type AlertPreference,
  type AlertPreferenceGroup,
  type AlertHistoryItem,
} from "../../../shared/api";
import {
  PREFERENCE_LABELS,
  deliveryStatusClass,
  messageFromUnknown,
} from "../../../shared/lib/dashboard-ui";
import { AlertRuleCard } from "./alerts/AlertRuleCard";
import { buildLeagueRulePayload, getLeagueFieldValue, ruleFieldsFor } from "./alerts/alert-rule-config";

export function AlertsView({ token }: { token: string }) {
  const [activeLeague, setActiveLeague] = useState<League>("NBA");
  const [busyAlertType, setBusyAlertType] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [preferenceGroups, setPreferenceGroups] = useState<AlertPreferenceGroup[]>([]);
  const [historyItems, setHistoryItems] = useState<AlertHistoryItem[]>([]);
  const [activeLeagues, setActiveLeagues] = useState<Array<{ league: League; label: string; alert_types: string[] }>>([]);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const [preferenceResponse, historyResponse, leaguesResponse] = await Promise.all([
        listAlertPreferences(token),
        listAlertHistory(token, { sinceHours: 24 * 7, limit: 100 }),
        listLeagues(),
      ]);
      setPreferenceGroups(preferenceResponse);
      setHistoryItems(historyResponse.items);
      setActiveLeagues(leaguesResponse);
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
    if (activeLeagues.length === 0) return;
    if (!activeLeagues.some((item) => item.league === activeLeague)) {
      setActiveLeague(activeLeagues[0].league);
    }
  }, [activeLeague, activeLeagues]);

  const onRuleFieldSettingChange = async (
    preference: AlertPreference,
    fieldKey: "close_game_margin_threshold" | "close_game_time_threshold_seconds" | "inning_start_threshold",
    fieldValue: number,
  ) => {
    setError(null);
    setBusyAlertType(`${preference.league}:${preference.alert_type}`);
    try {
      await updateAlertPreference(
        token,
        preference.league,
        preference.alert_type,
        buildLeagueRulePayload(preference, { fieldKey, fieldValue }),
      );
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
    const activeLeagueItem = activeLeagues.find((item) => item.league === activeLeague);
    const allowed = new Set(activeLeagueItem?.alert_types ?? []);
    return {
      ...raw,
      preferences: raw.preferences.filter((preference) => allowed.has(preference.alert_type)),
    };
  }, [preferenceGroups, activeLeague, activeLeagues]);

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
                {activeLeagues.map((league) => (
                  <button key={league.league} className={`chip-btn ${activeLeague === league.league ? "active" : ""}`.trim()} type="button" onClick={() => setActiveLeague(league.league)}>{league.label}</button>
                ))}
              </div>
            </div>

            {activeGroup ? (
              <ul className="list">
                {activeGroup.preferences.map((preference) => {
                  const fields = ruleFieldsFor(preference.alert_type, preference.is_enabled);
                  const inlineField = fields.length === 1 ? fields[0] : null;
                  return (
                    <AlertRuleCard
                      key={`${preference.league}:${preference.alert_type}`}
                      title={PREFERENCE_LABELS[preference.alert_type] ?? preference.alert_type}
                      isDisabled={!preference.is_enabled}
                      endSlot={
                        <div className="alert-rule-header-end">
                          {inlineField ? (
                            <label className="alert-inline-field">{inlineField.label}
                              <select
                                className="alert-rule-select"
                                value={getLeagueFieldValue(preference, inlineField)}
                                onChange={(event) => {
                                  onRuleFieldSettingChange(preference, inlineField.key, Number(event.target.value)).catch((requestError) =>
                                    setError(messageFromUnknown(requestError)),
                                  );
                                }}
                                disabled={busyAlertType === `${preference.league}:${preference.alert_type}`}
                              >
                                {inlineField.options.map((value) => <option key={value} value={value}>{value}</option>)}
                              </select>
                            </label>
                          ) : null}
                          <button
                            className={`alert-toggle ${preference.is_enabled ? "on" : "off"}`}
                            type="button"
                            role="switch"
                            aria-checked={preference.is_enabled}
                            disabled={busyAlertType === `${preference.league}:${preference.alert_type}`}
                            onClick={async () => {
                              setError(null);
                              setBusyAlertType(`${preference.league}:${preference.alert_type}`);
                              try {
                                await updateAlertPreference(
                                  token,
                                  preference.league,
                                  preference.alert_type,
                                  buildLeagueRulePayload(preference, { is_enabled: !preference.is_enabled }),
                                );
                                await load();
                              } catch (requestError) {
                                setError(messageFromUnknown(requestError));
                              } finally {
                                setBusyAlertType(null);
                              }
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
                                className="alert-rule-select"
                                value={getLeagueFieldValue(preference, field)}
                                onChange={(event) => {
                                  onRuleFieldSettingChange(preference, field.key, Number(event.target.value)).catch((requestError) =>
                                    setError(messageFromUnknown(requestError)),
                                  );
                                }}
                                disabled={busyAlertType === `${preference.league}:${preference.alert_type}`}
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
