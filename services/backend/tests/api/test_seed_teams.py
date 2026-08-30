from sqlalchemy import func, select

from app.db.models import CompetitionTeam, Team
from app.db.session import SessionLocal
from app.services.competitions import competition_teams_query
from app.services.seed import ensure_seeded_teams
from app.services.team_catalog import (
    FBS_TEAM_CONFERENCES,
    FBS_TEAMS_BY_CONFERENCE,
    TEAM_SEEDS_BY_COMPETITION,
)


def test_ensure_seeded_teams_reconciles_catalog_without_deleting_unknown_teams():
    with SessionLocal() as db:
        ensure_seeded_teams(db)

        nba_id, nba_name, nba_abbreviation = TEAM_SEEDS_BY_COMPETITION["NBA"][0]
        nba = db.scalar(
            competition_teams_query("NBA").where(Team.external_team_id == nba_id)
        )
        assert nba is not None
        nba.name = "Stale name"
        nba.abbreviation = "OLD"

        mls_id, mls_name, mls_abbreviation = TEAM_SEEDS_BY_COMPETITION["MLS"][0]
        mls = db.scalar(
            competition_teams_query("MLS").where(Team.external_team_id == mls_id)
        )
        assert mls is not None
        db.delete(mls)
        db.add(
            Team(
                sport="soccer",
                provider_scope="test",
                external_team_id="unknown",
                name="Unknown Club",
                abbreviation="UNK",
            )
        )
        db.commit()

        ensure_seeded_teams(db)
        ensure_seeded_teams(db)

        restored_nba = db.scalar(
            competition_teams_query("NBA").where(Team.external_team_id == nba_id)
        )
        restored_mls = db.scalar(
            competition_teams_query("MLS").where(Team.external_team_id == mls_id)
        )
        unknown = db.scalar(select(Team).where(Team.provider_scope == "test"))

        assert restored_nba is not None
        assert (restored_nba.name, restored_nba.abbreviation) == (
            nba_name,
            nba_abbreviation,
        )
        assert restored_mls is not None
        assert (restored_mls.name, restored_mls.abbreviation) == (
            mls_name,
            mls_abbreviation,
        )
        assert unknown is not None
        seeded_team_count = sum(
            len(teams) for teams in TEAM_SEEDS_BY_COMPETITION.values()
        )
        assert (
            db.scalar(select(func.count()).select_from(Team)) == seeded_team_count + 1
        )


def test_ensure_seeded_teams_preserves_discovered_fbs_opponents():
    with SessionLocal() as db:
        ensure_seeded_teams(db)
        opponent = Team(
            sport="football",
            provider_scope="cfb",
            external_team_id="999999",
            name="Example State Bears",
            abbreviation="EXST",
        )
        db.add(opponent)
        db.flush()
        db.add(CompetitionTeam(competition="FBS", team_id=opponent.id))
        db.commit()

        ensure_seeded_teams(db)

        assert (
            db.scalar(
                competition_teams_query("FBS").where(Team.external_team_id == "999999")
            )
            is not None
        )


def test_ensure_seeded_teams_assigns_every_fbs_program_to_a_conference():
    catalog_ids = [
        external_team_id
        for teams in FBS_TEAMS_BY_CONFERENCE.values()
        for external_team_id, _, _ in teams
    ]
    assert len(FBS_TEAMS_BY_CONFERENCE) == 11
    assert len(catalog_ids) == len(set(catalog_ids)) == 138
    assert set(FBS_TEAM_CONFERENCES) == {
        external_team_id for external_team_id, _, _ in TEAM_SEEDS_BY_COMPETITION["FBS"]
    }
    assert FBS_TEAM_CONFERENCES["333"] == "SEC"

    with SessionLocal() as db:
        ensure_seeded_teams(db)
        memberships = db.scalars(
            select(CompetitionTeam).where(CompetitionTeam.competition == "FBS")
        ).all()

        assert len(memberships) == 138
