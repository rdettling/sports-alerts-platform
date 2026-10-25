import { useCallback, useEffect, useMemo, useState } from "react";

import {
  listAlertHistory,
  listAlertPreferences,
  updateAlertPreference,
  type AlertHistoryItem,
  type AlertPreference,
  type AlertPreferenceGroup,
  type Competition,
} from "../../shared/api";
import { PREFERENCE_LABELS, messageFromUnknown } from "../../shared/lib/dashboard-ui";
import { CompetitionTabs } from "../../shared/components/DashboardFilters";
import { AlertDeliverySettings } from "./AlertDeliverySettings";
import { PeriodSelection } from "../../shared/components/PeriodSelection";
import { AlertRuleCard } from "../../shared/components/AlertRuleCard";
import {
  type AlertSettingsChange,
  buildAlertSettingsPayload,
  getRuleFieldValue,
  ruleFieldsFor,
} from "../../shared/lib/alert-rule-config";

function localDayKey(dateIso: string): string {
  const date = new Date(dateIso);
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function historyDayLabel(dateIso: string): string {
  const date = new Date(dateIso);
  const today = new Date(Date.now());
  if (localDayKey(dateIso) === localDayKey(today.toISOString())) return "Today";

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (localDayKey(dateIso) === localDayKey(yesterday.toISOString())) return "Yesterday";

  return date.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
}

export function AlertsView({ token }: { token: string }) {
  const [activeCompetition, setActiveCompetition] = useState<Competition | null>(null);
  const [busyAlertType, setBusyAlertType] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [preferenceGroups, setPreferenceGroups] = useState<AlertPreferenceGroup[]>([]);
  const [historyItems, setHistoryItems] = useState<AlertHistoryItem[]>([]);

  const loadAlertData = useCallback(
    async (showLoading = false) => {
      setError(null);
      if (showLoading) setLoading(true);
      try {
        const [preferenceResponse, historyResponse] = await Promise.all([
          listAlertPreferences(token),
          listAlertHistory(token, { sinceHours: 24 * 7, limit: 100 }),
        ]);
        setPreferenceGroups(preferenceResponse);
        setHistoryItems(historyResponse.items);
        setActiveCompetition((current) =>
          current && preferenceResponse.some((item) => item.competition === current)
            ? current
            : (preferenceResponse[0]?.competition ?? null),
        );
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [token],
  );

  useEffect(() => {
    loadAlertData(true).catch((loadError) => setError(messageFromUnknown(loadError)));
  }, [loadAlertData]);

  useEffect(() => {
    const id = window.setInterval(() => {
      loadAlertData().catch((loadError) => setError(messageFromUnknown(loadError)));
    }, 120_000);
    return () => window.clearInterval(id);
  }, [loadAlertData]);

  const updateRule = async (preference: AlertPreference, change: AlertSettingsChange) => {
    const busyKey = `${preference.competition}:${preference.alert_type}`;
    setError(null);
    setBusyAlertType(busyKey);
    try {
      const updated = await updateAlertPreference(
        token,
        preference.competition,
        preference.alert_type,
        buildAlertSettingsPayload(preference, change),
      );
      setPreferenceGroups((groups) =>
        groups.map((group) =>
          group.competition === updated.competition
            ? {
                ...group,
                preferences: group.preferences.map((item) =>
                  item.alert_type === updated.alert_type ? updated : item,
                ),
              }
            : group,
        ),
      );
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const activeGroup = useMemo(() => {
    if (!activeCompetition) return null;
    return preferenceGroups.find((group) => group.competition === activeCompetition) ?? null;
  }, [activeCompetition, preferenceGroups]);

  const historyGroups = useMemo(() => {
    const groups: Array<{ key: string; label: string; items: AlertHistoryItem[] }> = [];
    historyItems.forEach((item) => {
      const key = localDayKey(item.triggered_at);
      const current = groups[groups.length - 1];
      if (current?.key === key) {
        current.items.push(item);
      } else {
        groups.push({ key, label: historyDayLabel(item.triggered_at), items: [item] });
      }
    });
    return groups;
  }, [historyItems]);

  return (
    <section className="view-stack alerts-page" aria-label="Alerts">
      {error ? (
        <p className="error view-feedback" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? (
        <p className="muted view-feedback" role="status">
          Loading alerts...
        </p>
      ) : null}

      {!loading ? (
        <div className="alerts-layout">
          <AlertDeliverySettings token={token} />

          <div className="alerts-workspace">
            <section
              className="alerts-panel alerts-rules-panel surface"
              aria-labelledby="alert-rules-title"
            >
              <div className="alerts-panel-header alerts-rules-header surface-header">
                <h2 id="alert-rules-title">Alert Rules</h2>
                <CompetitionTabs
                  ariaLabel="Rule league"
                  options={preferenceGroups.map((group) => ({
                    value: group.competition,
                    label: group.label,
                  }))}
                  value={activeCompetition}
                  onChange={setActiveCompetition}
                />
              </div>

              <div className="alerts-rules-scroll">
                {activeGroup?.preferences.length ? (
                  <ul className="alert-rule-list">
                    {activeGroup.preferences.map((preference) => {
                      const label =
                        PREFERENCE_LABELS[preference.alert_type] ?? preference.alert_type;
                      const fields = ruleFieldsFor(preference.alert_type, preference.is_enabled);
                      const isBusy =
                        busyAlertType === `${preference.competition}:${preference.alert_type}`;
                      return (
                        <AlertRuleCard
                          key={`${preference.competition}:${preference.alert_type}`}
                          title={label}
                          isDisabled={!preference.is_enabled}
                          endSlot={
                            <div className="alert-rule-header-end">
                              <button
                                className={`alert-toggle ${preference.is_enabled ? "on" : "off"}`}
                                type="button"
                                role="switch"
                                aria-label={`${label} alerts`}
                                aria-checked={preference.is_enabled}
                                disabled={isBusy}
                                onClick={() =>
                                  void updateRule(preference, {
                                    is_enabled: !preference.is_enabled,
                                  })
                                }
                              >
                                <span className="alert-toggle-label" aria-hidden>
                                  {preference.is_enabled ? "On" : "Off"}
                                </span>
                                <span className="alert-toggle-track" aria-hidden>
                                  <span className="alert-toggle-thumb" />
                                </span>
                              </button>
                            </div>
                          }
                          controls={
                            preference.alert_type === "quarter_start" ||
                            preference.alert_type === "period_start" ||
                            preference.alert_type === "inning_start" ? (
                              <PeriodSelection
                                alertType={preference.alert_type}
                                periods={preference.periods ?? []}
                                disabled={isBusy || !preference.is_enabled}
                                onChange={(periods) => void updateRule(preference, { periods })}
                              />
                            ) : fields.length > 0 ? (
                              <>
                                {fields.map((field) => (
                                  <label key={field.key}>
                                    {field.label}
                                    <select
                                      className="alert-rule-select"
                                      value={getRuleFieldValue(preference, field)}
                                      onChange={(event) =>
                                        void updateRule(preference, {
                                          fieldKey: field.key,
                                          fieldValue: Number(event.target.value),
                                        })
                                      }
                                      disabled={isBusy}
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
                            ) : undefined
                          }
                        />
                      );
                    })}
                  </ul>
                ) : (
                  <p className="muted alerts-empty">No rules for this league.</p>
                )}
              </div>
            </section>

            <section
              className="alerts-panel alerts-history-panel surface"
              aria-labelledby="alert-history-title"
            >
              <div className="alerts-panel-header surface-header">
                <div>
                  <h2 id="alert-history-title">Alert History</h2>
                  <p>Last 7 days · {historyItems.length} events</p>
                </div>
              </div>

              <div className="alerts-history-scroll">
                {historyGroups.length ? (
                  <div className="alert-history-days">
                    {historyGroups.map((group) => (
                      <section
                        key={group.key}
                        className="alert-history-day"
                        aria-labelledby={`alert-history-${group.key}`}
                      >
                        <div className="alert-history-day-header">
                          <h3 id={`alert-history-${group.key}`}>{group.label}</h3>
                          <span>{group.items.length}</span>
                        </div>
                        <ul className="alert-history-list">
                          {group.items.map((item) => (
                            <li key={item.id} className="alert-history-row">
                              <div className="alert-history-event">
                                <time dateTime={item.triggered_at}>
                                  {new Date(item.triggered_at).toLocaleTimeString([], {
                                    hour: "numeric",
                                    minute: "2-digit",
                                  })}
                                </time>
                                <strong>
                                  {item.away_team_abbreviation} @ {item.home_team_abbreviation}
                                </strong>
                                <span>{PREFERENCE_LABELS[item.alert_type] ?? item.alert_type}</span>
                              </div>
                              <div className="alert-history-deliveries">
                                {item.deliveries.length ? (
                                  item.deliveries.map((delivery) => (
                                    <span
                                      key={delivery.channel}
                                      className={`alert-delivery-status status-${delivery.status}`}
                                    >
                                      {delivery.channel.charAt(0).toUpperCase() +
                                        delivery.channel.slice(1)}{" "}
                                      {delivery.status}
                                    </span>
                                  ))
                                ) : (
                                  <span className="alert-history-no-delivery">—</span>
                                )}
                              </div>
                            </li>
                          ))}
                        </ul>
                      </section>
                    ))}
                  </div>
                ) : (
                  <p className="muted alerts-empty">No alert history yet.</p>
                )}
              </div>
            </section>
          </div>
        </div>
      ) : null}
    </section>
  );
}
