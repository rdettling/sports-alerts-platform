import { useEffect, useState } from "react";

import { listUpdates, type SportsUpdate } from "../../../shared/api";
import { messageFromUnknown } from "../../../shared/lib/dashboard-ui";

function formatPublishedAt(value: string | null): string {
  if (!value) return "Unknown time";
  return new Date(value).toLocaleString();
}

export function UpdatesView({ token }: { token: string }) {
  const [items, setItems] = useState<SportsUpdate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const response = await listUpdates(token, 40);
      setItems(response.items);
    } catch (requestError) {
      setError(messageFromUnknown(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, [token]);

  useEffect(() => {
    const id = window.setInterval(() => {
      load().catch(() => undefined);
    }, 120_000);
    return () => window.clearInterval(id);
  }, [token]);

  return (
    <section className="view-stack">
      <section className="panel">
        {error ? <p className="error">{error}</p> : null}
        {loading ? <p className="muted">Loading updates...</p> : null}
        {!loading && items.length === 0 ? <p className="muted">No feed items yet.</p> : null}
        {!loading ? (
          <ul className="list">
            {items.map((item) => (
              <li key={item.id} className="row-card">
                <div className="following-followed-team-text">
                  <strong>{item.title}</strong>
                  <span className="muted">
                    {item.league} • {item.source_name} • {formatPublishedAt(item.published_at)}
                  </span>
                  <span className="muted">
                    {item.matched_scope === "team" ? "Matched by team" : "Matched by league"}
                    {item.team_abbreviations.length > 0 ? ` • ${item.team_abbreviations.join(", ")}` : ""}
                  </span>
                  {item.summary ? <span>{item.summary}</span> : null}
                  {item.reason ? <span className="muted">{item.reason}</span> : null}
                </div>
                <a className="btn btn-secondary" href={item.article_url} target="_blank" rel="noreferrer">
                  Open
                </a>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </section>
  );
}
