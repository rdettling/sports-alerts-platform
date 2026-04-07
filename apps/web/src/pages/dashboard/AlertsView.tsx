import { useCallback, useEffect, useMemo, useState } from "react";

import {
  AlertHistoryItem,
  AlertPreference,
  AlertType,
  Team,
  listAlertHistory,
  listAlertPreferences,
  listTeams,
  updateAlertPreference,
} from "../../api";
import { ALERT_TYPE_LABELS, PREFERENCE_LABELS, TeamLogo, deliveryStatusClass, messageFromUnknown } from "./shared";

export function AlertsView({ token }: { token: string }) {
  const [preferences, setPreferences] = useState<AlertPreference[]>([]);
  const [items, setItems] = useState<AlertHistoryItem[]>([]);
  const [last24hItems, setLast24hItems] = useState<AlertHistoryItem[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [alertTypeFilter, setAlertTypeFilter] = useState<"all" | AlertType>("all");
  const [timeFilter, setTimeFilter] = useState<"24h" | "7d" | "all">("24h");
  const [statusFilter, setStatusFilter] = useState<"all" | "sent" | "failed" | "pending">("all");
  const [closeGameMarginInput, setCloseGameMarginInput] = useState(5);
  const [closeGameMinutesInput, setCloseGameMinutesInput] = useState(2);
  const [busyAlertType, setBusyAlertType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [preferenceResponse, historyResponse, history24Response, teamsResponse] = await Promise.all([
        listAlertPreferences(token),
        listAlertHistory(token, {
          alertType: alertTypeFilter === "all" ? undefined : alertTypeFilter,
          sinceHours: timeFilter === "24h" ? 24 : timeFilter === "7d" ? 24 * 7 : undefined,
          limit: 200,
        }),
        listAlertHistory(token, { sinceHours: 24, limit: 200 }),
        listTeams(),
      ]);
      setPreferences(preferenceResponse);
      const closePref = preferenceResponse.find((preference) => preference.alert_type === "close_game_late");
      if (closePref) {
        setCloseGameMarginInput(closePref.close_game_margin_threshold ?? 5);
        setCloseGameMinutesInput(Math.max(1, Math.round((closePref.close_game_time_threshold_seconds ?? 120) / 60)));
      }
      setItems(historyResponse.items);
      setLast24hItems(history24Response.items);
      setTeams(teamsResponse);
      setUpdatedAt(new Date());
    } finally {
      setLoading(false);
    }
  }, [alertTypeFilter, timeFilter, token]);

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, [load]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
    }, 120_000);
    return () => window.clearInterval(intervalId);
  }, [load]);

  const onToggle = async (preference: AlertPreference) => {
    setError(null);
    setBusyAlertType(preference.alert_type);
    try {
      await updateAlertPreference(token, preference.alert_type, { is_enabled: !preference.is_enabled });
      await load();
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const onCloseGameSettingChange = async (nextMargin: number, nextMinutes: number) => {
    const closePref = preferences.find((preference) => preference.alert_type === "close_game_late");
    if (!closePref) return;
    setError(null);
    setBusyAlertType("close_game_late");
    try {
      await updateAlertPreference(token, "close_game_late", {
        is_enabled: closePref.is_enabled,
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

  const filteredItems = useMemo(() => {
    if (statusFilter === "all") {
      return items;
    }
    return items.filter((item) => item.delivery_status === statusFilter);
  }, [items, statusFilter]);

  const sent24hCount = useMemo(
    () => last24hItems.filter((item) => item.delivery_status === "sent").length,
    [last24hItems],
  );
  const failed24hCount = useMemo(
    () => last24hItems.filter((item) => item.delivery_status === "failed").length,
    [last24hItems],
  );
  const lastSentAt = useMemo(() => {
    const sentItem = last24hItems.find((item) => item.delivery_status === "sent");
    return sentItem ? new Date(sentItem.sent_at).toLocaleString() : "No sent alerts in last 24h";
  }, [last24hItems]);
  const teamsByAbbreviation = useMemo(
    () => new Map(teams.map((team) => [team.abbreviation.toUpperCase(), team])),
    [teams],
  );

  return (
    <section className="card">
      <div className="alerts-header">
        <h2>Alerts</h2>
        <span className="muted">{updatedAt ? `Updated ${updatedAt.toLocaleTimeString()}` : "Loading..."}</span>
      </div>
      {error ? <p className="error">{error}</p> : null}

      <div className="alerts-health-grid">
        <div className="alerts-health-card">
          <span className="muted">Last sent</span>
          <strong>{lastSentAt}</strong>
        </div>
        <div className="alerts-health-card">
          <span className="muted">Sent (24h)</span>
          <strong>{sent24hCount}</strong>
        </div>
        <div className="alerts-health-card">
          <span className="muted">Failed (24h)</span>
          <strong>{failed24hCount}</strong>
        </div>
      </div>

      {loading ? <p>Loading alert settings and history...</p> : null}

      {!loading ? (
        <div className="alerts-grid">
          <div className="alerts-panel">
            <h3>Alert Rules</h3>
            <ul className="list">
              {preferences.map((preference) => (
                <li
                  key={preference.alert_type}
                  className={`row-card alert-rule-row ${preference.is_enabled ? "" : "alert-rule-disabled"}`.trim()}
                >
                  <div className="alert-rule-content">
                    <div className="alert-rule-header">
                      <div className="alert-rule-title-wrap">
                        <strong>{PREFERENCE_LABELS[preference.alert_type] ?? preference.alert_type}</strong>
                      </div>
                      <button
                        className={`alert-toggle ${preference.is_enabled ? "on" : "off"}`}
                        type="button"
                        role="switch"
                        aria-checked={preference.is_enabled}
                        aria-label={`Toggle ${PREFERENCE_LABELS[preference.alert_type] ?? preference.alert_type}`}
                        disabled={busyAlertType === preference.alert_type}
                        onClick={() => onToggle(preference)}
                      >
                        <span className="alert-toggle-track">
                          <span className="alert-toggle-thumb" />
                        </span>
                      </button>
                    </div>
                    {preference.alert_type === "close_game_late" && preference.is_enabled ? (
                      <div className="alert-rule-controls">
                        <label>
                          Margin
                          <select
                            className="alert-rule-select"
                            value={closeGameMarginInput}
                            onChange={(event) => {
                              const nextMargin = Number(event.target.value);
                              setCloseGameMarginInput(nextMargin);
                              onCloseGameSettingChange(nextMargin, closeGameMinutesInput).catch((requestError) =>
                                setError(messageFromUnknown(requestError)),
                              );
                            }}
                            disabled={busyAlertType === "close_game_late"}
                          >
                            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Minutes
                          <select
                            className="alert-rule-select"
                            value={closeGameMinutesInput}
                            onChange={(event) => {
                              const nextMinutes = Number(event.target.value);
                              setCloseGameMinutesInput(nextMinutes);
                              onCloseGameSettingChange(closeGameMarginInput, nextMinutes).catch((requestError) =>
                                setError(messageFromUnknown(requestError)),
                              );
                            }}
                            disabled={busyAlertType === "close_game_late"}
                          >
                            {[1, 2, 3, 4, 5, 10].map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    ) : null}
                    {preference.alert_type === "close_game_late" && !preference.is_enabled ? (
                      <span className="muted alert-rule-subtext">Enable this rule to configure margin and minute thresholds.</span>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="alerts-panel">
            <h3>Recent Alerts</h3>
            <div className="alerts-filters">
              <select value={alertTypeFilter} onChange={(event) => setAlertTypeFilter(event.target.value as "all" | AlertType)}>
                <option value="all">All alert types</option>
                <option value="game_start">Game start</option>
                <option value="close_game_late">Close game late</option>
                <option value="final_result">Final result</option>
              </select>
              <select value={timeFilter} onChange={(event) => setTimeFilter(event.target.value as "24h" | "7d" | "all")}>
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
                <option value="all">All time</option>
              </select>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | "sent" | "failed" | "pending")}>
                <option value="all">All statuses</option>
                <option value="sent">Sent</option>
                <option value="failed">Failed</option>
                <option value="pending">Pending</option>
              </select>
            </div>
            {filteredItems.length === 0 ? <p className="muted">No alerts in this filter.</p> : null}
            <ul className="list">
              {filteredItems.map((item) => (
                <li key={item.id} className="row-card">
                  <span className="alert-history-row-main">
                    <span>{new Date(item.sent_at).toLocaleString()}</span>
                    <span className="team-row">
                      {teamsByAbbreviation.get(item.away_team_abbreviation) ? (
                        <TeamLogo team={teamsByAbbreviation.get(item.away_team_abbreviation)!} size={18} />
                      ) : (
                        <span className="team-logo-fallback" style={{ width: 18, height: 18 }}>
                          {item.away_team_abbreviation.slice(0, 2)}
                        </span>
                      )}
                      <strong>{item.away_team_abbreviation}</strong>
                      <span className="muted">@</span>
                      {teamsByAbbreviation.get(item.home_team_abbreviation) ? (
                        <TeamLogo team={teamsByAbbreviation.get(item.home_team_abbreviation)!} size={18} />
                      ) : (
                        <span className="team-logo-fallback" style={{ width: 18, height: 18 }}>
                          {item.home_team_abbreviation.slice(0, 2)}
                        </span>
                      )}
                      <strong>{item.home_team_abbreviation}</strong>
                    </span>
                    <span>{ALERT_TYPE_LABELS[item.alert_type] ?? item.alert_type}</span>
                  </span>
                  <span className={`chip ${deliveryStatusClass(item.delivery_status)}`}>{item.delivery_status}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </section>
  );
}
