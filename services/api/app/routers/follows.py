from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Game, Team, User, UserGameFollow, UserTeamFollow
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.follow import CurrentFollowsOut
from app.schemas.game import GameOut
from app.schemas.team import TeamOut

router = APIRouter(prefix="/follows", tags=["follows"])


@router.get("", response_model=CurrentFollowsOut)
def list_current_follows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentFollowsOut:
    teams = db.scalars(
        select(Team)
        .join(UserTeamFollow, UserTeamFollow.team_id == Team.id)
        .where(UserTeamFollow.user_id == current_user.id)
        .order_by(Team.name.asc())
    ).all()
    games = db.scalars(
        select(Game)
        .join(UserGameFollow, UserGameFollow.game_id == Game.id)
        .where(UserGameFollow.user_id == current_user.id)
        .order_by(Game.scheduled_start_time.asc())
    ).all()
    return CurrentFollowsOut(
        teams=[TeamOut.model_validate(team) for team in teams],
        games=[GameOut.model_validate(game) for game in games],
    )


@router.post("/teams/{team_id}", status_code=status.HTTP_201_CREATED)
def follow_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    existing = db.scalar(
        select(UserTeamFollow).where(UserTeamFollow.user_id == current_user.id, UserTeamFollow.team_id == team_id)
    )
    if existing:
        return {"status": "already_following"}

    db.add(UserTeamFollow(user_id=current_user.id, team_id=team_id, created_at=datetime.now(timezone.utc)))
    db.commit()
    return {"status": "followed"}


@router.delete("/teams/{team_id}")
def unfollow_team(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    existing = db.scalar(
        select(UserTeamFollow).where(UserTeamFollow.user_id == current_user.id, UserTeamFollow.team_id == team_id)
    )
    if not existing:
        return {"status": "not_following"}
    db.delete(existing)
    db.commit()
    return {"status": "unfollowed"}


@router.post("/games/{game_id}", status_code=status.HTTP_201_CREATED)
def follow_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")

    existing = db.scalar(
        select(UserGameFollow).where(UserGameFollow.user_id == current_user.id, UserGameFollow.game_id == game_id)
    )
    if existing:
        return {"status": "already_following"}

    db.add(UserGameFollow(user_id=current_user.id, game_id=game_id, created_at=datetime.now(timezone.utc)))
    db.commit()
    return {"status": "followed"}


@router.delete("/games/{game_id}")
def unfollow_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    existing = db.scalar(
        select(UserGameFollow).where(UserGameFollow.user_id == current_user.id, UserGameFollow.game_id == game_id)
    )
    if not existing:
        return {"status": "not_following"}
    db.delete(existing)
    db.commit()
    return {"status": "unfollowed"}

