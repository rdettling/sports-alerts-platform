from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CompetitionTeam, Team, User
from app.services.competitions import (
    ensure_competition_settings,
    get_competition_profile,
)
from app.services.team_catalog import COMPETITION_TEAM_IDS, TEAM_CATALOG


def ensure_seeded_teams(db: Session) -> None:
    ensure_competition_settings(db)
    existing_teams = {
        (team.provider_scope, team.external_team_id): team
        for team in db.scalars(
            select(Team).where(
                Team.provider_scope.in_({scope for scope, _ in TEAM_CATALOG})
            )
        ).all()
    }
    for (provider_scope, external_team_id), (
        sport,
        name,
        abbreviation,
    ) in TEAM_CATALOG.items():
        team = existing_teams.get((provider_scope, external_team_id))
        if team is None:
            team = Team(
                sport=sport,
                provider_scope=provider_scope,
                external_team_id=external_team_id,
                name=name,
                abbreviation=abbreviation,
            )
            db.add(team)
            db.flush()
            existing_teams[(provider_scope, external_team_id)] = team
        else:
            team.sport = sport
            team.name = name
            team.abbreviation = abbreviation

    desired_memberships = {
        (
            competition,
            existing_teams[(profile.provider_team_scope, external_team_id)].id,
        )
        for competition, external_team_ids in COMPETITION_TEAM_IDS.items()
        for profile in (get_competition_profile(competition),)
        for external_team_id in external_team_ids
    }
    existing_memberships = db.scalars(
        select(CompetitionTeam).where(
            CompetitionTeam.competition.in_(COMPETITION_TEAM_IDS)
        )
    ).all()
    existing_membership_keys = {
        (membership.competition, membership.team_id)
        for membership in existing_memberships
    }
    cfb_team_ids = set(db.scalars(select(Team.id).where(Team.provider_scope == "cfb")))
    for membership in existing_memberships:
        if membership.competition == "FBS" and membership.team_id in cfb_team_ids:
            continue
        if (membership.competition, membership.team_id) not in desired_memberships:
            db.delete(membership)
    db.add_all(
        CompetitionTeam(competition=competition, team_id=team_id)
        for competition, team_id in sorted(
            desired_memberships - existing_membership_keys
        )
    )
    db.commit()


def ensure_bootstrap_admin(db: Session, email: str) -> None:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        db.add(User(email=normalized_email, role="admin"))
        db.commit()
        return
    if user.role != "admin":
        user.role = "admin"
        db.commit()
