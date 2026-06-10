from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select, union
from sqlalchemy.orm import Session

from app.db.models import Game, Team, User, UserGameFollow, UserGameUnfollow, UserLeagueFollow, UserTeamFollow
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.follow import CurrentFollowsOut, LeagueFollowOut
from app.schemas.game import GameOut
from app.schemas.team import TeamOut

router = APIRouter(prefix="/follows", tags=["follows"])


@router.get("", response_model=CurrentFollowsOut)
def list_current_follows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentFollowsOut:
    leagues = db.scalars(
        select(UserLeagueFollow)
        .where(UserLeagueFollow.user_id == current_user.id)
        .order_by(UserLeagueFollow.league.asc())
    ).all()

    teams = db.scalars(
        select(Team)
        .join(UserTeamFollow, UserTeamFollow.team_id == Team.id)
        .where(UserTeamFollow.user_id == current_user.id)
        .order_by(Team.name.asc())
    ).all()

    followed_team_ids = select(UserTeamFollow.team_id).where(UserTeamFollow.user_id == current_user.id)
    unfollowed_game_ids = select(UserGameUnfollow.game_id).where(UserGameUnfollow.user_id == current_user.id)

    explicit_game_ids = select(UserGameFollow.game_id).where(UserGameFollow.user_id == current_user.id)
    team_game_ids = (
        select(Game.id.label("game_id"))
        .where(or_(Game.home_team_id.in_(followed_team_ids), Game.away_team_id.in_(followed_team_ids)))
        .where(~Game.id.in_(unfollowed_game_ids))
    )
    effective_game_ids = union(explicit_game_ids, team_game_ids).subquery()

    games = db.scalars(
        select(Game)
        .join(effective_game_ids, effective_game_ids.c.game_id == Game.id)
        .order_by(Game.scheduled_start_time.asc())
    ).all()
    return CurrentFollowsOut(
        leagues=[LeagueFollowOut(league=row.league) for row in leagues],
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


@router.post("/leagues/{league}", status_code=status.HTTP_201_CREATED)
def follow_league(
    league: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    normalized = league.strip().upper()
    if normalized not in {"NBA", "MLB"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid league")

    existing = db.scalar(
        select(UserLeagueFollow).where(UserLeagueFollow.user_id == current_user.id, UserLeagueFollow.league == normalized)
    )
    if existing:
        return {"status": "already_following"}

    db.add(UserLeagueFollow(user_id=current_user.id, league=normalized, created_at=datetime.now(timezone.utc)))
    db.commit()
    return {"status": "followed"}


@router.delete("/leagues/{league}")
def unfollow_league(
    league: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    normalized = league.strip().upper()
    if normalized not in {"NBA", "MLB"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid league")

    existing = db.scalar(
        select(UserLeagueFollow).where(UserLeagueFollow.user_id == current_user.id, UserLeagueFollow.league == normalized)
    )
    if not existing:
        return {"status": "not_following"}
    db.delete(existing)
    db.commit()
    return {"status": "unfollowed"}


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

    existing_unfollow = db.scalar(
        select(UserGameUnfollow).where(UserGameUnfollow.user_id == current_user.id, UserGameUnfollow.game_id == game_id)
    )
    if existing_unfollow:
        db.delete(existing_unfollow)

    db.add(UserGameFollow(user_id=current_user.id, game_id=game_id, created_at=datetime.now(timezone.utc)))
    db.commit()
    return {"status": "followed"}


@router.delete("/games/{game_id}")
def unfollow_game(
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
        db.delete(existing)

    follows_team_in_game = db.scalar(
        select(UserTeamFollow.id).where(
            UserTeamFollow.user_id == current_user.id,
            or_(UserTeamFollow.team_id == game.home_team_id, UserTeamFollow.team_id == game.away_team_id),
        )
    )
    if follows_team_in_game:
        existing_unfollow = db.scalar(
            select(UserGameUnfollow).where(UserGameUnfollow.user_id == current_user.id, UserGameUnfollow.game_id == game_id)
        )
        if not existing_unfollow:
            db.add(UserGameUnfollow(user_id=current_user.id, game_id=game_id, created_at=datetime.now(timezone.utc)))
        db.commit()
        return {"status": "unfollowed"}

    if not existing:
        return {"status": "not_following"}

    db.commit()
    return {"status": "unfollowed"}
