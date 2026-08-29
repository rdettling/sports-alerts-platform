import { apiUrl } from "../client";

export function subscribeToGameUpdates(onUpdate: () => void): () => void {
  if (typeof EventSource === "undefined") return () => undefined;

  const source = new EventSource(apiUrl("/updates/games"));
  source.addEventListener("games", onUpdate);
  return () => source.close();
}
