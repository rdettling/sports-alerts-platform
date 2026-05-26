import { useEffect, useMemo, useState } from "react";

import {
  listAlertHistory,
  listAlertPreferences,
  listTeams,
  updateAlertPreference,
  type AlertHistoryItem,
  type AlertPreference,
  type AlertPreferenceGroup,
  type AlertType,
  type Team,
} from "../../../shared/api";
import { ALERT_TYPE_LABELS, PREFERENCE_LABELS, TeamLogo, deliveryStatusClass, messageFromUnknown } from "../../../shared/lib/dashboard-ui";
import { useDashboardShell } from "./shell";

export function AlertsView({ token }: { token: string }) {
  const { setLastSync } = useDashboardShell();

  const [alertTypeFilter, setAlertTypeFilter] = useState<"all" | AlertType>("all");
  const [timeFilter, setTimeFilter] = useState<"24h" | "7d" | "all">("24h");
  const [statusFilter, setStatusFilter] = useState<"all" | "sent" | "failed" | "pending">("all");
  const [busyAlertType, setBusyAlertType] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [preferenceGroups, setPreferenceGroups] = useState<AlertPreferenceGroup[]>([]);
  const [items, setItems] = useState<AlertHistoryItem[]>([]);
  const [last24hItems, setLast24hItems] = useState<AlertHistoryItem[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const load = async () => {
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
      setPreferenceGroups(preferenceResponse);
      setItems(historyResponse.items);
      setLast24hItems(history24Response.items);
      setTeams(teamsResponse);
      const now = new Date();
      setUpdatedAt(now);
      setLastSync(now);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch((loadError) => setError(messageFromUnknown(loadError)));
  }, [token, alertTypeFilter, timeFilter]);

  useEffect(() => {
    const id = window.setInterval(() => {
      load().catch((loadError) => setError(messageFromUnknown(loadError)));
    }, 120_000);
    return () => window.clearInterval(id);
  }, [token, alertTypeFilter, timeFilter]);

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

  const filteredItems = useMemo(
    () => (statusFilter === "all" ? items : items.filter((item) => item.delivery_status === statusFilter)),
    [items, statusFilter],
  );
  const sent24hCount = useMemo(() => last24hItems.filter((item) => item.delivery_status === "sent").length, [last24hItems]);
  const failed24hCount = useMemo(() => last24hItems.filter((item) => item.delivery_status === "failed").length, [last24hItems]);
  const lastSentAt = useMemo(() => {
    const sentItem = last24hItems.find((item) => item.delivery_status === "sent");
    return sentItem ? new Date(sentItem.sent_at).toLocaleString() : "No sent alerts in last 24h";
  }, [last24hItems]);
  const teamsByAbbreviation = useMemo(() => new Map(teams.map((team) => [team.abbreviation.toUpperCase(), team])), [teams]);

  return (
    <section className="view-stack">
      <div className="metric-grid">
        <article className="metric-card"><span>Last sent</span><strong>{lastSentAt}</strong></article>
        <article className="metric-card"><span>Sent (24h)</span><strong>{sent24hCount}</strong></article>
        <article className="metric-card"><span>Failed (24h)</span><strong>{failed24hCount}</strong></article>
        <article className="metric-card"><span>Updated</span><strong>{updatedAt ? updatedAt.toLocaleTimeString() : "Loading..."}</strong></article>
      </div>

      {error ? <p className="error">{error}</p> : null}
      {loading ? <p className="muted">Loading alert settings and history...</p> : null}

      {!loading ? (
        <div className="alerts-layout">
          <section className="panel">
            <div className="section-header"><h3>Alert Rules</h3><p>Enable delivery rules and tune close-game sensitivity.</p></div>
            {preferenceGroups.map((group) => (
              <div key={group.league} className="alert-league-section">
                <h4>{group.league} Defaults</h4>
                <ul className="list">
                  {group.preferences.map((preference) => (
                    <li key={`${group.league}:${preference.alert_type}`} className={`row-card alert-rule-row ${preference.is_enabled ? "" : "alert-rule-disabled"}`.trim()}>
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
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>

          <section className="panel">
            <div className="section-header section-header-inline"><div><h3>Recent Alerts</h3><p>Filter by type, status, and time window.</p></div></div>
            <div className="toolbar sticky-toolbar">
              <select value={alertTypeFilter} onChange={(event) => setAlertTypeFilter(event.target.value as "all" | AlertType)}><option value="all">All alert types</option><option value="game_start">Game start</option><option value="close_game_late">Close game late</option><option value="final_result">Final result</option></select>
              <select value={timeFilter} onChange={(event) => setTimeFilter(event.target.value as "24h" | "7d" | "all")}><option value="24h">Last 24 hours</option><option value="7d">Last 7 days</option><option value="all">All time</option></select>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | "sent" | "failed" | "pending")}><option value="all">All statuses</option><option value="sent">Sent</option><option value="failed">Failed</option><option value="pending">Pending</option></select>
            </div>
            {filteredItems.length === 0 ? <p className="muted">No alerts in this filter.</p> : null}
            <ul className="list">
              {filteredItems.map((item) => (
                <li key={item.id} className="row-card">
                  <span className="alert-history-row-main">
                    <span>{new Date(item.sent_at).toLocaleString()}</span>
                    <span className="team-row">
                      {teamsByAbbreviation.get(item.away_team_abbreviation) ? <TeamLogo team={teamsByAbbreviation.get(item.away_team_abbreviation)!} size={18} /> : <span className="team-logo-fallback" style={{ width: 18, height: 18 }}>{item.away_team_abbreviation.slice(0, 2)}</span>}
                      <strong>{item.away_team_abbreviation}</strong><span className="muted">@</span>
                      {teamsByAbbreviation.get(item.home_team_abbreviation) ? <TeamLogo team={teamsByAbbreviation.get(item.home_team_abbreviation)!} size={18} /> : <span className="team-logo-fallback" style={{ width: 18, height: 18 }}>{item.home_team_abbreviation.slice(0, 2)}</span>}
                      <strong>{item.home_team_abbreviation}</strong>
                    </span>
                    <span>{ALERT_TYPE_LABELS[item.alert_type] ?? item.alert_type}</span>
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
