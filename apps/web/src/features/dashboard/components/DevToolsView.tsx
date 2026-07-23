import { useEffect, useMemo, useState } from "react";

import { AlertType, League, Team, listLeagues, listTeams, sendDevTestEmail, type LeagueSetting } from "../../../shared/api";
import {
  TeamLogo,
  PREFERENCE_LABELS,
  messageFromUnknown,
} from "../../../shared/lib/dashboard-ui";

export function DevToolsView({ token }: { token: string }) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeLeague, setActiveLeague] = useState<League>("NBA");
  const [activeLeagues, setActiveLeagues] = useState<LeagueSetting[]>([]);
  const [busyAlertType, setBusyAlertType] = useState<AlertType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setError(null);
      setLoading(true);
      try {
        const [teamsResponse, leaguesResponse] = await Promise.all([listTeams(), listLeagues()]);
        setTeams(teamsResponse);
        setActiveLeagues(leaguesResponse);
      } catch (fetchError) {
        setError(messageFromUnknown(fetchError));
      } finally {
        setLoading(false);
      }
    };
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, []);

  useEffect(() => {
    if (activeLeagues.length === 0) return;
    if (!activeLeagues.some((item) => item.league === activeLeague)) {
      setActiveLeague(activeLeagues[0].league);
    }
  }, [activeLeague, activeLeagues]);

  const onSendTest = async (alertType: AlertType) => {
    setError(null);
    setResult(null);
    setBusyAlertType(alertType);
    try {
      const response = await sendDevTestEmail(token, { league: activeLeague, alert_type: alertType });
      const message = `${PREFERENCE_LABELS[response.alert_type] ?? response.alert_type} sent for ${response.league.replace("_", " ")}.`;
      setResult(message);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const syntheticTeams = useMemo(() => {
    const leagueTeams = teams.filter((team) => team.league === activeLeague);
    if (leagueTeams.length < 2) {
      return { away: null, home: null };
    }
    const matchup = activeLeagues.find((item) => item.league === activeLeague)?.default_test_matchup;
    const byAbbreviation = new Map(leagueTeams.map((team) => [team.abbreviation.toUpperCase(), team] as const));
    const away = matchup ? byAbbreviation.get(matchup[0]) : undefined;
    const home = matchup ? byAbbreviation.get(matchup[1]) : undefined;
    if (away && home && away.id !== home.id) {
      return { away, home };
    }
    return { away: leagueTeams[0], home: leagueTeams[1] };
  }, [teams, activeLeague, activeLeagues]);
  const activeLeagueItem = activeLeagues.find((item) => item.league === activeLeague) ?? null;
  const activeAlertTypes = (activeLeagueItem?.alert_types ?? []) as AlertType[];

  return (
    <section className="card admin-tools-card">
      <div className="admin-tools-body">
        <div className="admin-tools-intro">
          <h3>Test alert actions</h3>
          <p className="muted">Queue one synthetic pending alert to validate delivery flow.</p>
        </div>
        <div className="chip-row">
          {activeLeagues.map((league) => (
            <button
              key={league.league}
              className={`chip-btn ${activeLeague === league.league ? "active" : ""}`.trim()}
              type="button"
              onClick={() => setActiveLeague(league.league)}
            >
              {league.label}
            </button>
          ))}
        </div>

        <div className="admin-tools-matchup">
          <span className="admin-tools-label">Synthetic matchup ({activeLeagueItem?.label ?? activeLeague})</span>
          <span className="admin-tools-matchup-row">
            {syntheticTeams.away ? <TeamLogo team={syntheticTeams.away} size={20} /> : null}
            <strong>{syntheticTeams.away?.abbreviation ?? "AWAY"}</strong>
            <span className="muted">@</span>
            {syntheticTeams.home ? <TeamLogo team={syntheticTeams.home} size={20} /> : null}
            <strong>{syntheticTeams.home?.abbreviation ?? "HOME"}</strong>
          </span>
        </div>

        <div className="admin-action-list">
          {activeAlertTypes.map((alertType) => (
            <button
              key={alertType}
              className="admin-test-btn"
              type="button"
              disabled={loading || busyAlertType !== null || !syntheticTeams.away || !syntheticTeams.home}
              onClick={() => onSendTest(alertType)}
            >
              <span>{PREFERENCE_LABELS[alertType] ?? alertType} alert</span>
              <span className="admin-test-btn-meta">Queue now</span>
            </button>
          ))}
        </div>

        {loading ? <p>Loading test tool data...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {result ? <p className="admin-result">{result}</p> : null}
      </div>
    </section>
  );
}
