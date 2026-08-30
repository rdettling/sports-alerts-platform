from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CompetitionTeam, Game
from app.schemas.game import GameOut, TeamStrengthOut


def build_game_outs(db: Session, games: Sequence[Game]) -> list[GameOut]:
    game_views = [GameOut.model_validate(game) for game in games]
    if not games:
        return game_views

    team_ids = {team_id for game in games for team_id in (game.home_team_id, game.away_team_id)}
    competitions = {game.competition for game in games}
    strength_rows = db.scalars(
        select(CompetitionTeam).where(
            CompetitionTeam.competition.in_(competitions),
            CompetitionTeam.team_id.in_(team_ids),
        )
    ).all()
    strengths = {(row.competition, row.team_id): TeamStrengthOut.model_validate(row) for row in strength_rows}
    for game, game_view in zip(games, game_views, strict=True):
        game_view.home_team_strength = strengths.get((game.competition, game.home_team_id), TeamStrengthOut())
        game_view.away_team_strength = strengths.get((game.competition, game.away_team_id), TeamStrengthOut())
    return game_views
