import { useEffect, useMemo, useState } from "react";

import { AlertType, League, Team, listTeams, sendDevTestEmail } from "../../../shared/api";
import { TeamLogo, messageFromUnknown } from "../../../shared/lib/dashboard-ui";

const ALERT_TYPES_BY_LEAGUE: Record<League, AlertType[]> = {
  NBA: ["game_start", "close_game_late", "final_result"],
  MLB: ["game_start", "inning_start", "final_result"],
};
const DEFAULT_TEST_MATCHUP_BY_LEAGUE: Record<League, { away: string; home: string }> = {
  NBA: { away: "ATL", home: "BOS" },
  MLB: { away: "MIA", home: "TOR" },
};

export function DevToolsView({ token }: { token: string }) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeLeague, setActiveLeague] = useState<League>("NBA");
  const [busyAlertType, setBusyAlertType] = useState<AlertType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  useEffect(() => {
    const load = async () => {
      setError(null);
      setLoading(true);
      try {
        const teamsResponse = await listTeams();
        setTeams(teamsResponse);
      } catch (fetchError) {
        setError(messageFromUnknown(fetchError));
      } finally {
        setLoading(false);
      }
    };
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, []);

  const onSendTest = async (alertType: AlertType) => {
    setError(null);
    setResult(null);
    setBusyAlertType(alertType);
    try {
      const response = await sendDevTestEmail(token, { league: activeLeague, alert_type: alertType });
      const message = `Queued ${response.league} ${response.alert_type} alert on synthetic game #${response.game_id}. Status: ${response.delivery_status}.`;
      setResult(message);
      setHistory((current) => [message, ...current].slice(0, 10));
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const syntheticTeams = useMemo(() => {
    const leagueTeams = teams.filter((team) => (team.league || "").toUpperCase() === activeLeague);
    if (leagueTeams.length < 2) {
      return { away: null, home: null };
    }
    const byAbbr = new Map(leagueTeams.map((team) => [team.abbreviation.toUpperCase(), team]));
    const defaults = DEFAULT_TEST_MATCHUP_BY_LEAGUE[activeLeague];
    const away = byAbbr.get(defaults.away);
    const home = byAbbr.get(defaults.home);
    if (away && home && away.id !== home.id) {
      return { away, home };
    }
    return { away: leagueTeams[0], home: leagueTeams[1] };
  }, [teams, activeLeague]);
  const activeAlertTypes = ALERT_TYPES_BY_LEAGUE[activeLeague];

  return (
    <section className="card admin-tools-card">
      <div className="admin-tools-body">
        <div className="admin-tools-intro">
          <h3>Test alert actions</h3>
          <p className="muted">Queue one synthetic pending alert to validate delivery flow.</p>
        </div>
        <div className="chip-row">
          <button
            className={`chip-btn ${activeLeague === "NBA" ? "active" : ""}`.trim()}
            type="button"
            onClick={() => setActiveLeague("NBA")}
          >
            NBA
          </button>
          <button
            className={`chip-btn ${activeLeague === "MLB" ? "active" : ""}`.trim()}
            type="button"
            onClick={() => setActiveLeague("MLB")}
          >
            MLB
          </button>
        </div>

        <div className="admin-tools-matchup">
          <span className="admin-tools-label">Synthetic matchup ({activeLeague})</span>
          <span className="team-row">
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
              <span>{alertType === "game_start" ? "Game start alert" : alertType === "close_game_late" ? "Close-game alert" : alertType === "inning_start" ? "Inning-start alert" : "Final-result alert"}</span>
              <span className="admin-test-btn-meta">Queue now</span>
            </button>
          ))}
        </div>

        {loading ? <p>Loading test tool data...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {result ? <p className="admin-result">{result}</p> : null}
        {history.length > 0 ? (
          <section className="admin-panel admin-panel-scroll">
            <h3>Recent actions</h3>
            <div className="admin-scroll-body">
              <ul className="list">
                {history.map((entry, index) => (
                  <li key={`${entry}-${index}`} className="admin-action-history-row">
                    {entry}
                  </li>
                ))}
              </ul>
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}
