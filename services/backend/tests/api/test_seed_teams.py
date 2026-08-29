from sqlalchemy import func, select

from app.db.models import CompetitionTeam, Team
from app.db.session import SessionLocal
from app.services.competitions import competition_teams_query, get_competition_profile
from app.services.seed import ensure_seeded_teams
from app.services.team_catalog import (
    COMPETITION_TEAM_IDS,
    FBS_TEAM_CONFERENCES,
    FBS_TEAMS_BY_CONFERENCE,
    TEAM_CATALOG,
)


def test_ensure_seeded_teams_reconciles_catalog_without_deleting_unknown_teams():
    with SessionLocal() as db:
        ensure_seeded_teams(db)

        nba_id = COMPETITION_TEAM_IDS["NBA"][0]
        nba_profile = get_competition_profile("NBA")
        _, nba_name, nba_abbreviation = TEAM_CATALOG[(nba_profile.provider_team_scope, nba_id)]
        nba = db.scalar(competition_teams_query("NBA").where(Team.external_team_id == nba_id))
        assert nba is not None
        nba.name = "Stale name"
        nba.abbreviation = "OLD"

        mls_id = COMPETITION_TEAM_IDS["MLS"][0]
        mls_profile = get_competition_profile("MLS")
        _, mls_name, mls_abbreviation = TEAM_CATALOG[(mls_profile.provider_team_scope, mls_id)]
        mls = db.scalar(competition_teams_query("MLS").where(Team.external_team_id == mls_id))
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

        restored_nba = db.scalar(competition_teams_query("NBA").where(Team.external_team_id == nba_id))
        restored_mls = db.scalar(competition_teams_query("MLS").where(Team.external_team_id == mls_id))
        unknown = db.scalar(select(Team).where(Team.provider_scope == "test"))

        assert restored_nba is not None
        assert (restored_nba.name, restored_nba.abbreviation) == (nba_name, nba_abbreviation)
        assert restored_mls is not None
        assert (restored_mls.name, restored_mls.abbreviation) == (mls_name, mls_abbreviation)
        assert unknown is not None
        assert db.scalar(select(func.count()).select_from(Team)) == len(TEAM_CATALOG) + 1


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

        assert db.scalar(
            competition_teams_query("FBS").where(Team.external_team_id == "999999")
        ) is not None


def test_ensure_seeded_teams_assigns_every_fbs_program_to_a_conference():
    catalog_ids = [
        external_team_id
        for teams in FBS_TEAMS_BY_CONFERENCE.values()
        for external_team_id, _, _ in teams
    ]
    assert len(FBS_TEAMS_BY_CONFERENCE) == 11
    assert len(catalog_ids) == len(set(catalog_ids)) == 138
    assert set(FBS_TEAM_CONFERENCES) == set(COMPETITION_TEAM_IDS["FBS"])
    assert FBS_TEAM_CONFERENCES["333"] == "SEC"

    with SessionLocal() as db:
        ensure_seeded_teams(db)
        memberships = db.scalars(
            select(CompetitionTeam).where(CompetitionTeam.competition == "FBS")
        ).all()

        assert len(memberships) == 138
