import { useEffect, useMemo, useState } from "react";

import { AlertType, Team, listTeams, sendDevTestEmail } from "../../api";
import { TeamLogo, messageFromUnknown } from "./shared";

const TEST_ALERT_TYPES: AlertType[] = ["game_start", "close_game_late", "final_result"];
const DEFAULT_TEST_AWAY_ABBR = "ATL";
const DEFAULT_TEST_HOME_ABBR = "BOS";

function resolveSyntheticTeams(teams: Team[]): { away: Team | null; home: Team | null } {
  if (teams.length < 2) {
    return { away: null, home: null };
  }
  const byAbbr = new Map(teams.map((team) => [team.abbreviation.toUpperCase(), team]));
  const away = byAbbr.get(DEFAULT_TEST_AWAY_ABBR);
  const home = byAbbr.get(DEFAULT_TEST_HOME_ABBR);
  if (away && home && away.id !== home.id) {
    return { away, home };
  }
  return { away: teams[0], home: teams[1] };
}

function labelForAlertType(alertType: AlertType): string {
  if (alertType === "game_start") {
    return "Queue game start alert";
  }
  if (alertType === "close_game_late") {
    return "Queue close-game alert";
  }
  return "Queue final-result alert";
}

export function DevToolsView({ token }: { token: string }) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [busyAlertType, setBusyAlertType] = useState<AlertType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

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
      const response = await sendDevTestEmail(token, { alert_type: alertType });
      setResult(`Queued ${response.alert_type} alert on synthetic game #${response.game_id}. Status: ${response.delivery_status}.`);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  const syntheticTeams = useMemo(() => resolveSyntheticTeams(teams), [teams]);

  return (
    <section className="card admin-tools-card">
      <div className="following-header admin-tools-header">
        <h2>Admin Tools</h2>
      </div>
      <div className="admin-tools-body">
        <p className="muted">Each action generates a synthetic test game (default ATL @ BOS) and queues one pending alert for your user.</p>

        <div className="admin-tools-matchup">
          <span className="admin-tools-label">Synthetic matchup</span>
          <span className="team-row">
            {syntheticTeams.away ? <TeamLogo team={syntheticTeams.away} size={20} /> : null}
            <strong>{syntheticTeams.away?.abbreviation ?? "AWAY"}</strong>
            <span className="muted">@</span>
            {syntheticTeams.home ? <TeamLogo team={syntheticTeams.home} size={20} /> : null}
            <strong>{syntheticTeams.home?.abbreviation ?? "HOME"}</strong>
          </span>
        </div>

        <div className="admin-action-list">
          {TEST_ALERT_TYPES.map((alertType) => (
            <button
              key={alertType}
              className="admin-test-btn"
              type="button"
              disabled={loading || busyAlertType !== null || !syntheticTeams.away || !syntheticTeams.home}
              onClick={() => onSendTest(alertType)}
            >
              {labelForAlertType(alertType)}
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
