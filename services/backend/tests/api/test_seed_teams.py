from sqlalchemy import func, select

from app.db.models import Team
from app.db.session import SessionLocal
from app.services.seed import TEAM_SEEDS_BY_LEAGUE, ensure_seeded_teams


def test_ensure_seeded_teams_reconciles_catalog_without_deleting_unknown_teams():
    with SessionLocal() as db:
        ensure_seeded_teams(db)

        nba_id, nba_name, nba_abbreviation = TEAM_SEEDS_BY_LEAGUE["NBA"][0]
        nba = db.scalar(select(Team).where(Team.league == "NBA", Team.external_team_id == nba_id))
        assert nba is not None
        nba.name = "Stale name"
        nba.abbreviation = "OLD"

        mls_id, mls_name, mls_abbreviation = TEAM_SEEDS_BY_LEAGUE["MLS"][0]
        mls = db.scalar(select(Team).where(Team.league == "MLS", Team.external_team_id == mls_id))
        assert mls is not None
        db.delete(mls)
        db.add(Team(external_team_id="unknown", league="MLS", name="Unknown Club", abbreviation="UNK"))
        db.commit()

        ensure_seeded_teams(db)
        ensure_seeded_teams(db)

        restored_nba = db.scalar(select(Team).where(Team.league == "NBA", Team.external_team_id == nba_id))
        restored_mls = db.scalar(select(Team).where(Team.league == "MLS", Team.external_team_id == mls_id))
        unknown = db.scalar(select(Team).where(Team.league == "MLS", Team.external_team_id == "unknown"))

        assert restored_nba is not None
        assert (restored_nba.name, restored_nba.abbreviation) == (nba_name, nba_abbreviation)
        assert restored_mls is not None
        assert (restored_mls.name, restored_mls.abbreviation) == (mls_name, mls_abbreviation)
        assert unknown is not None
        assert db.scalar(select(func.count()).select_from(Team)) == sum(
            len(teams) for teams in TEAM_SEEDS_BY_LEAGUE.values()
        ) + 1
