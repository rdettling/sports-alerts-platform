import { type Competition, type Game, type TeamStrength } from "../../../../shared/api";

type MarginBand = readonly [maximum: number, factor: number];

const FOOTBALL_COMPETITIONS = new Set<Competition>(["NFL", "FBS"]);
const SOCCER_COMPETITIONS = new Set<Competition>(["MLS", "LA_LIGA", "PREMIER_LEAGUE", "WORLD_CUP"]);

const FOOTBALL_QUARTER_SECONDS = 15 * 60;
const FOOTBALL_REGULATION_SECONDS = 4 * FOOTBALL_QUARTER_SECONDS;
const BASEBALL_REGULATION_HALF_INNINGS = 18;

const FOOTBALL_URGENCY_BASELINE = 0.45;
const BASEBALL_URGENCY_BASELINE = 0.55;
const BASKETBALL_URGENCY_BASELINE = 0.4;
const SOCCER_URGENCY_BASELINE = 0.55;

const MATCHUP_AVERAGE_WEIGHT = 0.85;
const MATCHUP_WEAKER_TEAM_WEIGHT = 0.15;
const LIVE_TEAM_QUALITY_BONUS = 15;
const PREGAME_FAVORITE_NON_WIN_THRESHOLD = 0.2;
const PREGAME_QUALIFIED_SCORE_FLOOR = 20;
const PREGAME_QUALIFIED_SCORE_RANGE = 80;
const ODDS_PREGAME_WINDOW_MS = 24 * 60 * 60 * 1000;

const FOOTBALL_MARGIN_BANDS: readonly MarginBand[] = [
  [0, 1],
  [3, 0.95],
  [8, 0.9],
  [16, 0.55],
  [24, 0.25],
  [Number.POSITIVE_INFINITY, 0],
];

const BASEBALL_MARGIN_BANDS: readonly MarginBand[] = [
  [0, 1],
  [1, 0.95],
  [2, 0.8],
  [3, 0.6],
  [5, 0.3],
  [Number.POSITIVE_INFINITY, 0],
];

const BASKETBALL_MARGIN_BANDS: readonly MarginBand[] = [
  [0, 1],
  [3, 0.95],
  [6, 0.9],
  [10, 0.8],
  [15, 0.75],
  [20, 0.4],
  [Number.POSITIVE_INFINITY, 0],
];

const SOCCER_MARGIN_BANDS: readonly MarginBand[] = [
  [0, 1],
  [1, 0.9],
  [2, 0.5],
  [3, 0.25],
  [Number.POSITIVE_INFINITY, 0],
];

export function footballRegulationSecondsRemaining(game: Game): number | null {
  if (!isLiveFootballGame(game) || game.period === null || game.period < 1) return null;
  if (game.period >= 5) return 0;

  const clockSeconds = parseFootballClock(game.clock);
  if (clockSeconds === null) return null;
  return (4 - game.period) * FOOTBALL_QUARTER_SECONDS + clockSeconds;
}

export function footballWatchabilityScore(game: Game): number | null {
  if (game.home_score === null || game.away_score === null) return null;
  const remainingSeconds = footballRegulationSecondsRemaining(game);
  if (remainingSeconds === null) return null;

  const progress =
    game.period !== null && game.period >= 5
      ? 1
      : 1 - remainingSeconds / FOOTBALL_REGULATION_SECONDS;
  return urgencyScore(
    marginFactor(Math.abs(game.home_score - game.away_score), FOOTBALL_MARGIN_BANDS),
    progress,
    FOOTBALL_URGENCY_BASELINE,
  );
}

export function baseballHalfInningsRemaining(game: Game): number | null {
  if (game.competition !== "MLB" || !isLiveGame(game) || game.period === null || game.period < 1) {
    return null;
  }
  if (game.period >= 10) return 0;

  const currentHalf = game.clock?.toLowerCase().includes("bottom") ? 1 : 0;
  const completedHalfInnings = (game.period - 1) * 2 + currentHalf;
  return BASEBALL_REGULATION_HALF_INNINGS - completedHalfInnings;
}

export function baseballWatchabilityScore(game: Game): number | null {
  if (game.home_score === null || game.away_score === null) return null;
  const remainingHalfInnings = baseballHalfInningsRemaining(game);
  if (remainingHalfInnings === null) return null;

  const progress =
    game.period !== null && game.period >= 10
      ? 1
      : 1 - remainingHalfInnings / BASEBALL_REGULATION_HALF_INNINGS;
  return urgencyScore(
    marginFactor(Math.abs(game.home_score - game.away_score), BASEBALL_MARGIN_BANDS),
    progress,
    BASEBALL_URGENCY_BASELINE,
  );
}

export function teamStrengthFactor(strength: TeamStrength, competition: Competition): number {
  const record = recordStrengthFactor(strength);
  if (competition !== "FBS") return record;

  if (strength.rank !== null && strength.rank >= 1 && strength.rank <= 25) {
    return 0.75 + (0.25 * (25 - strength.rank)) / 24;
  }
  return Math.min(record, 0.7);
}

export function matchupQualityFactor(game: Game): number {
  const home = teamStrengthFactor(game.home_team_strength, game.competition);
  const away = teamStrengthFactor(game.away_team_strength, game.competition);
  return (
    MATCHUP_AVERAGE_WEIGHT * ((home + away) / 2) + MATCHUP_WEAKER_TEAM_WEIGHT * Math.min(home, away)
  );
}

export function combinedTeamStrengthFactor(game: Game): number {
  const home = teamStrengthFactor(game.home_team_strength, game.competition);
  const away = teamStrengthFactor(game.away_team_strength, game.competition);
  return (home + away) / 2;
}

export function americanOddsImpliedProbability(odds: number): number | null {
  if (!Number.isInteger(odds) || Math.abs(odds) < 100) return null;
  return odds > 0 ? 100 / (odds + 100) : Math.abs(odds) / (Math.abs(odds) + 100);
}

export function normalizeProbabilities(probabilities: readonly number[]): number[] | null {
  if (
    probabilities.length < 2 ||
    probabilities.some((probability) => !Number.isFinite(probability) || probability <= 0)
  ) {
    return null;
  }

  const total = probabilities.reduce((sum, probability) => sum + probability, 0);
  return probabilities.map((probability) => probability / total);
}

export function marketCompetitivenessFactor(
  americanOdds: readonly (number | null)[],
): number | null {
  const normalized = normalizedAmericanOddsProbabilities(americanOdds);
  if (!normalized) return null;

  return competitivenessFromNormalizedProbabilities(normalized);
}

export function pregameMarketCompetitiveness(game: Game): number | null {
  const normalized = normalizedPregameProbabilities(game);
  return normalized ? competitivenessFromNormalizedProbabilities(normalized) : null;
}

export function pregameFavoriteNonWinProbability(game: Game): number | null {
  const normalized = normalizedPregameProbabilities(game);
  const outcomes = game.odds?.outcomes;
  if (!normalized || !outcomes) return null;

  const teamProbabilities = normalized.filter(
    (_, index) => outcomes[index].team_side === "home" || outcomes[index].team_side === "away",
  );
  return teamProbabilities.length === 2 ? 1 - Math.max(...teamProbabilities) : null;
}

export function pregameWatchabilityScore(game: Game): number {
  const favoriteNonWinProbability = pregameFavoriteNonWinProbability(game);
  if (
    favoriteNonWinProbability !== null &&
    favoriteNonWinProbability < PREGAME_FAVORITE_NON_WIN_THRESHOLD - Number.EPSILON
  ) {
    return 100 * favoriteNonWinProbability;
  }

  return (
    PREGAME_QUALIFIED_SCORE_FLOOR + PREGAME_QUALIFIED_SCORE_RANGE * combinedTeamStrengthFactor(game)
  );
}

export function basketballRegulationSecondsRemaining(game: Game): number | null {
  if (
    (game.competition !== "NBA" && game.competition !== "WNBA") ||
    !isLiveGame(game) ||
    game.period === null ||
    game.period < 1
  ) {
    return null;
  }
  if (game.period >= 5) return 0;

  const quarterSeconds = game.competition === "NBA" ? 12 * 60 : 10 * 60;
  const clockSeconds = parseBasketballClock(game.clock, quarterSeconds);
  if (clockSeconds === null) return null;
  return (4 - game.period) * quarterSeconds + clockSeconds;
}

export function basketballWatchabilityScore(game: Game): number | null {
  if (game.home_score === null || game.away_score === null) return null;
  const remainingSeconds = basketballGameSecondsRemaining(game);
  if (remainingSeconds === null) return null;

  const regulationSeconds = (game.competition === "NBA" ? 12 : 10) * 60 * 4;
  const progress = 1 - remainingSeconds / regulationSeconds;
  return urgencyScore(
    marginFactor(Math.abs(game.home_score - game.away_score), BASKETBALL_MARGIN_BANDS),
    progress,
    BASKETBALL_URGENCY_BASELINE,
  );
}

export function basketballGameSecondsRemaining(game: Game): number | null {
  if (game.period !== null && game.period >= 5) {
    if ((game.competition !== "NBA" && game.competition !== "WNBA") || !isLiveGame(game)) {
      return null;
    }
    return parseBasketballClock(game.clock, 5 * 60);
  }
  return basketballRegulationSecondsRemaining(game);
}

export function soccerRegulationMinutesRemaining(game: Game): number | null {
  if (
    !SOCCER_COMPETITIONS.has(game.competition) ||
    !isLiveGame(game) ||
    game.period === null ||
    game.period < 1
  ) {
    return null;
  }
  if (game.period >= 5) return 0;
  if (game.clock?.trim().match(/^(?:HT|halftime)$/i)) return 45;

  const elapsedMinutes = parseSoccerClock(game.clock);
  if (elapsedMinutes === null) return null;
  return Math.max(0, (game.period >= 3 ? 120 : 90) - elapsedMinutes);
}

export function soccerWatchabilityScore(game: Game): number | null {
  if (game.home_score === null || game.away_score === null) return null;
  const remainingMinutes = soccerRegulationMinutesRemaining(game);
  if (remainingMinutes === null) return null;

  const competitiveness =
    game.period !== null && game.period >= 5
      ? 1
      : marginFactor(Math.abs(game.home_score - game.away_score), SOCCER_MARGIN_BANDS);
  const progress = game.period !== null && game.period >= 3 ? 1 : 1 - remainingMinutes / 90;
  return urgencyScore(competitiveness, progress, SOCCER_URGENCY_BASELINE);
}

export function liveGameRemainingShare(game: Game): number | null {
  if (game.competition === "MLB") {
    const remaining = baseballHalfInningsRemaining(game);
    return remaining === null ? null : remaining / BASEBALL_REGULATION_HALF_INNINGS;
  }
  if (FOOTBALL_COMPETITIONS.has(game.competition)) {
    const remaining = footballRegulationSecondsRemaining(game);
    return remaining === null ? null : remaining / FOOTBALL_REGULATION_SECONDS;
  }
  if (game.competition === "NBA" || game.competition === "WNBA") {
    const remaining = basketballGameSecondsRemaining(game);
    const regulationSeconds = (game.competition === "NBA" ? 12 : 10) * 60 * 4;
    return remaining === null ? null : remaining / regulationSeconds;
  }
  const remaining = soccerRegulationMinutesRemaining(game);
  const regulationMinutes = game.period !== null && game.period >= 3 ? 120 : 90;
  return remaining === null ? null : remaining / regulationMinutes;
}

export function liveGameStagePriority(game: Game): number {
  if (!SOCCER_COMPETITIONS.has(game.competition) || game.period === null) return 0;
  if (game.period >= 5) return 2;
  return game.period >= 3 ? 1 : 0;
}

export function liveWatchabilityScore(game: Game): number | null {
  const urgency =
    game.competition === "MLB"
      ? baseballWatchabilityScore(game)
      : FOOTBALL_COMPETITIONS.has(game.competition)
        ? footballWatchabilityScore(game)
        : game.competition === "NBA" || game.competition === "WNBA"
          ? basketballWatchabilityScore(game)
          : soccerWatchabilityScore(game);
  if (urgency === null) return null;

  const qualityAboveNeutral = Math.max(0, (matchupQualityFactor(game) - 0.5) / 0.5);
  return Math.round(Math.min(100, urgency + LIVE_TEAM_QUALITY_BONUS * qualityAboveNeutral));
}

function marginFactor(margin: number, bands: readonly MarginBand[]): number {
  return bands.find(([maximum]) => margin <= maximum)?.[1] ?? 0;
}

function urgencyScore(competitiveness: number, progress: number, baseline: number): number {
  return Math.round(100 * competitiveness * (baseline + (1 - baseline) * progress));
}

function parseFootballClock(clock: string | null): number | null {
  const match = clock?.trim().match(/^(\d{1,2}):([0-5]\d)$/);
  if (!match) return null;
  const minutes = Number(match[1]);
  if (minutes > 15) return null;
  return minutes * 60 + Number(match[2]);
}

function parseBasketballClock(clock: string | null, quarterSeconds: number): number | null {
  const value = clock?.trim();
  if (!value) return null;

  const minuteClock = value.match(/^(\d{1,2}):([0-5]\d)$/);
  if (minuteClock) {
    const seconds = Number(minuteClock[1]) * 60 + Number(minuteClock[2]);
    return seconds <= quarterSeconds ? seconds : null;
  }

  if (!/^\d{1,2}\.\d+$/.test(value)) return null;
  const seconds = Number(value);
  return seconds >= 0 && seconds < 60 ? seconds : null;
}

function parseSoccerClock(clock: string | null): number | null {
  const match = clock?.trim().match(/^(\d{1,3})'(?:\+(\d{1,2})')?$/);
  if (!match) return null;
  return Number(match[1]) + Number(match[2] ?? 0);
}

function recordStrengthFactor(strength: TeamStrength): number {
  if (strength.wins === null || strength.losses === null) return 0.5;
  const ties = strength.ties ?? 0;
  const total = strength.wins + strength.losses + ties;
  return total > 0 ? (strength.wins + 0.5 * ties) / total : 0.5;
}

function normalizedAmericanOddsProbabilities(
  americanOdds: readonly (number | null)[],
): number[] | null {
  if (americanOdds.length !== 2 && americanOdds.length !== 3) return null;

  const implied: number[] = [];
  for (const price of americanOdds) {
    if (price === null) return null;
    const probability = americanOddsImpliedProbability(price);
    if (probability === null) return null;
    implied.push(probability);
  }
  return normalizeProbabilities(implied);
}

function competitivenessFromNormalizedProbabilities(probabilities: readonly number[]): number {
  const largestProbability = Math.max(...probabilities);
  const evenMarketRemainder = 1 - 1 / probabilities.length;
  return Math.max(0, Math.min(1, (1 - largestProbability) / evenMarketRemainder));
}

function normalizedPregameProbabilities(game: Game): number[] | null {
  const odds = game.odds;
  if (!odds?.last_update || !hasCompleteMoneyline(game)) return null;

  const kickoff = Date.parse(game.scheduled_start_time);
  const updated = Date.parse(odds.last_update);
  if (
    !Number.isFinite(kickoff) ||
    !Number.isFinite(updated) ||
    updated > kickoff ||
    kickoff - updated > ODDS_PREGAME_WINDOW_MS
  ) {
    return null;
  }

  return normalizedAmericanOddsProbabilities(
    odds.outcomes.map((outcome) => outcome.price_american),
  );
}

function hasCompleteMoneyline(game: Game): boolean {
  const outcomes = game.odds?.outcomes;
  const expectedOutcomeCount = SOCCER_COMPETITIONS.has(game.competition) ? 3 : 2;
  if (!outcomes || outcomes.length !== expectedOutcomeCount) return false;
  if (new Set(outcomes.map((outcome) => outcome.outcome_key)).size !== outcomes.length)
    return false;

  const homeCount = outcomes.filter((outcome) => outcome.team_side === "home").length;
  const awayCount = outcomes.filter((outcome) => outcome.team_side === "away").length;
  const drawCount = outcomes.filter(
    (outcome) => outcome.team_side === null && outcome.outcome_key === "draw",
  ).length;
  return homeCount === 1 && awayCount === 1 && drawCount === expectedOutcomeCount - 2;
}

function isLiveGame(game: Game): boolean {
  return !game.is_final && (game.status === "in_progress" || game.status === "live");
}

function isLiveFootballGame(game: Game): boolean {
  return FOOTBALL_COMPETITIONS.has(game.competition) && isLiveGame(game);
}
