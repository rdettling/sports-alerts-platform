import { type Sport } from "../api";

export const PREFERENCE_LABELS: Record<string, string> = {
  game_start: "Game start",
  close_game_late: "Close game late",
  overtime_start: "Overtime start",
  inning_start: "Inning start",
  extra_innings_start: "Extra innings start",
  second_half_start: "Second half start",
  extra_time_start: "Extra time start",
  penalty_kicks: "Penalty kicks",
  score_changed: "Score update",
  lead_change: "Lead change",
  final_result: "Final result",
};

export const SPORT_LABELS: Record<Sport, string> = {
  basketball: "Basketball",
  football: "Football",
  baseball: "Baseball",
  soccer: "Soccer",
};

export function messageFromUnknown(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}
