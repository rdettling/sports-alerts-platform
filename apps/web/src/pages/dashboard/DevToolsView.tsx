import { useEffect, useMemo, useState } from "react";

import { AlertType, Game, Team, listGames, listTeams, sendDevTestEmail } from "../../api";
import { TeamLogo, formatTipoff, messageFromUnknown } from "./shared";

const TEST_ALERT_TYPES: AlertType[] = ["game_start", "close_game_late", "final_result"];

function gameLabel(game: Game, teamMap: Map<number, Team>): string {
  const away = teamMap.get(game.away_team_id);
  const home = teamMap.get(game.home_team_id);
  const matchup = away && home ? `${away.abbreviation} @ ${home.abbreviation}` : `Game ${game.id}`;
  return `${formatTipoff(game.scheduled_start_time)} • ${matchup}`;
}

export function DevToolsView({ token }: { token: string }) {
  const [games, setGames] = useState<Game[]>([]);
  const [teamMap, setTeamMap] = useState<Map<number, Team>>(new Map());
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [busyAlertType, setBusyAlertType] = useState<AlertType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const [gamesResponse, teamsResponse] = await Promise.all([listGames(), listTeams()]);
      const sortedGames = [...gamesResponse].sort(
        (a, b) => new Date(a.scheduled_start_time).getTime() - new Date(b.scheduled_start_time).getTime(),
      );
      setGames(sortedGames);
      setTeamMap(new Map(teamsResponse.map((team) => [team.id, team])));
      if (!selectedGameId && sortedGames.length > 0) {
        setSelectedGameId(sortedGames[0].id);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch((fetchError) => setError(messageFromUnknown(fetchError)));
  }, []);

  const selectedGame = useMemo(() => games.find((game) => game.id === selectedGameId) ?? null, [games, selectedGameId]);

  const onSendTest = async (alertType: AlertType) => {
    setError(null);
    setResult(null);
    setBusyAlertType(alertType);
    try {
      const response = await sendDevTestEmail(token, {
        alert_type: alertType,
        game_id: selectedGameId ?? undefined,
      });
      setResult(`Queued ${response.alert_type} test email for game #${response.game_id}. Status: ${response.delivery_status}.`);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setBusyAlertType(null);
    }
  };

  return (
    <section className="card">
      <div className="following-header">
        <h2>Dev Tools</h2>
        <button className="btn-secondary" disabled={loading || busyAlertType !== null} onClick={() => load().catch((fetchError) => setError(messageFromUnknown(fetchError)))}>
          Refresh
        </button>
      </div>
      <p className="muted">Create real pending alerts for your user so the worker sends test emails.</p>

      <label>
        Target game
        <select
          value={selectedGameId ?? ""}
          onChange={(event) => setSelectedGameId(Number(event.target.value))}
          disabled={loading || games.length === 0}
        >
          {games.map((game) => (
            <option key={game.id} value={game.id}>
              {gameLabel(game, teamMap)}
            </option>
          ))}
        </select>
      </label>

      {selectedGame ? (
        <div className="row-card">
          <span className="team-row">
            {teamMap.get(selectedGame.away_team_id) ? (
              <TeamLogo team={teamMap.get(selectedGame.away_team_id)!} size={20} />
            ) : null}
            <strong>{teamMap.get(selectedGame.away_team_id)?.abbreviation ?? "AWAY"}</strong>
            <span className="muted">@</span>
            {teamMap.get(selectedGame.home_team_id) ? (
              <TeamLogo team={teamMap.get(selectedGame.home_team_id)!} size={20} />
            ) : null}
            <strong>{teamMap.get(selectedGame.home_team_id)?.abbreviation ?? "HOME"}</strong>
            <span className="muted">• {formatTipoff(selectedGame.scheduled_start_time)}</span>
          </span>
        </div>
      ) : null}

      <div className="inline-form">
        {TEST_ALERT_TYPES.map((alertType) => (
          <button
            key={alertType}
            type="button"
            disabled={loading || busyAlertType !== null || games.length === 0}
            onClick={() => onSendTest(alertType)}
          >
            Send {alertType} test
          </button>
        ))}
      </div>

      {loading ? <p>Loading dev test data...</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {result ? <p>{result}</p> : null}
    </section>
  );
}
