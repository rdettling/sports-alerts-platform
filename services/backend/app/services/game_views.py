from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CompetitionTeam, Game, Team
from app.schemas.game import GameOut, GameTeamOut, TeamStrengthOut
from app.services.team_catalog import FBS_TEAM_CONFERENCES


def build_game_outs(db: Session, games: Sequence[Game]) -> list[GameOut]:
    if not games:
        return []

    team_ids = {team_id for game in games for team_id in (game.home_team_id, game.away_team_id)}
    teams = {
        team.id: team
        for team in db.scalars(select(Team).where(Team.id.in_(team_ids))).all()
    }
    competitions = {game.competition for game in games}
    strength_rows = db.scalars(
        select(CompetitionTeam).where(
            CompetitionTeam.competition.in_(competitions),
            CompetitionTeam.team_id.in_(team_ids),
        )
    ).all()
    strengths = {(row.competition, row.team_id): TeamStrengthOut.model_validate(row) for row in strength_rows}
    def build_team(team: Team) -> GameTeamOut:
        return GameTeamOut(
            id=team.id,
            sport=team.sport,
            external_team_id=team.external_team_id,
            name=team.name,
            abbreviation=team.abbreviation,
            conference=(
                FBS_TEAM_CONFERENCES.get(team.external_team_id)
                if team.provider_scope == "cfb"
                else None
            ),
        )

    return [
        GameOut(
            **{
                field: getattr(game, field)
                for field in GameOut.model_fields
                if hasattr(game, field)
            },
            home_team=build_team(teams[game.home_team_id]),
            away_team=build_team(teams[game.away_team_id]),
            home_team_strength=strengths.get(
                (game.competition, game.home_team_id), TeamStrengthOut()
            ),
            away_team_strength=strengths.get(
                (game.competition, game.away_team_id), TeamStrengthOut()
            ),
        )
        for game in games
    ]
