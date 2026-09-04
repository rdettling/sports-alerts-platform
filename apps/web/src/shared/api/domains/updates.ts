import { apiUrl } from "../client";

export function subscribeToGameUpdates(onUpdate: () => void, onOpen: () => void): () => void {
  if (typeof EventSource === "undefined") return () => undefined;

  const source = new EventSource(apiUrl("/updates/games"));
  source.addEventListener("games", onUpdate);
  source.addEventListener("open", onOpen);
  return () => source.close();
}
