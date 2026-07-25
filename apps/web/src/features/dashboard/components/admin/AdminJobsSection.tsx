import { useEffect, useState } from "react";

import { type OpsAdminSummaryResponse } from "../../../../shared/api";
import { leagueBadgeLabel, leagueLogoUrl } from "../../../../shared/lib/dashboard-ui";
import { buildLeagueJobGroups } from "./admin-jobs";
import { formatAdminDateTime } from "./admin-format";

export function AdminJobsSection({ summary }: { summary: OpsAdminSummaryResponse }) {
  const leagueJobGroups = buildLeagueJobGroups(summary);
  const [selectedLeague, setSelectedLeague] = useState(leagueJobGroups[0]?.league.league ?? "");

  useEffect(() => {
    if (!leagueJobGroups.some(({ league }) => league.league === selectedLeague)) {
      setSelectedLeague(leagueJobGroups[0]?.league.league ?? "");
    }
  }, [leagueJobGroups, selectedLeague]);

  const activeGroup =
    leagueJobGroups.find(({ league }) => league.league === selectedLeague) ??
    leagueJobGroups[0] ??
    null;

  if (!activeGroup) {
    return (
      <section className="card admin-section admin-section-compact">
        <div className="admin-section-head">
          <div>
            <h3>Jobs</h3>
            <p className="muted">No enabled leagues are available.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="card admin-section admin-section-compact admin-jobs-layout">
      <aside className="admin-jobs-sidebar" aria-label="League selector">
        {leagueJobGroups.map(({ league }) => {
          const isActive = league.league === activeGroup.league.league;
          const logoUrl = leagueLogoUrl(league.league);

          return (
            <button
              key={league.league}
              type="button"
              className={`admin-jobs-league-button ${isActive ? "active" : ""}`}
              aria-pressed={isActive}
              onClick={() => setSelectedLeague(league.league)}
            >
              <span className="admin-jobs-league-mark" aria-hidden="true">
                {logoUrl ? (
                  <img
                    className={`admin-jobs-league-logo league-${league.league.toLowerCase()}`}
                    src={logoUrl}
                    alt=""
                  />
                ) : (
                  <span className="admin-jobs-league-fallback">
                    {leagueBadgeLabel(league.league)}
                  </span>
                )}
              </span>
              <span className="admin-jobs-league-copy">
                <strong>{league.label}</strong>
                <span className="muted">{league.is_enabled ? "Enabled" : "Disabled"}</span>
              </span>
            </button>
          );
        })}
      </aside>

      <div className="admin-jobs-detail">
        <div className="admin-section-head">
          <div>
            <h3>{activeGroup.league.label}</h3>
            <p className="muted">Current catalog and live sync schedule for this league.</p>
          </div>
        </div>
        <div className="admin-league-jobs-grid">
          <article className="admin-sync-card">
            <div className="admin-sync-card-head">
              <strong>Catalog sync</strong>
              <span className="admin-job-status">
                {activeGroup.catalogJob?.status ?? "missing"}
              </span>
            </div>
            <div className="admin-sync-card-meta">
              <div>
                <span className="muted">Next sync</span>
                <strong>{formatAdminDateTime(activeGroup.catalogJob?.next_run_at)}</strong>
              </div>
              <div>
                <span className="muted">Previous sync</span>
                <strong>{formatAdminDateTime(activeGroup.catalogJob?.last_success_at)}</strong>
              </div>
            </div>
          </article>

          <article className="admin-sync-card">
            <div className="admin-sync-card-head">
              <strong>Live sync</strong>
              <span className="admin-job-status">{activeGroup.liveJob?.status ?? "missing"}</span>
            </div>
            <div className="admin-sync-card-meta">
              <div>
                <span className="muted">Next sync</span>
                <strong>{formatAdminDateTime(activeGroup.liveJob?.next_run_at)}</strong>
              </div>
              <div>
                <span className="muted">Previous sync</span>
                <strong>{formatAdminDateTime(activeGroup.liveJob?.last_success_at)}</strong>
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
