export type GameStateTone = "scheduled" | "live" | "final" | "postponed";

export function GameStatePill({
  text,
  tone,
}: {
  text: string;
  tone: GameStateTone;
}) {
  return <span className={`games-status-pill ${tone}`.trim()}>{text}</span>;
}
