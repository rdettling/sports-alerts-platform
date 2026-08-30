from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.deps import get_current_user
from app.schemas.competition_visibility import (
    CompetitionVisibilityOut,
    UpdateCompetitionVisibilityRequest,
)
from app.services.competitions import list_supported_competitions, normalize_competition

router = APIRouter(prefix="/competition-visibility", tags=["competition-visibility"])
SUPPORTED_COMPETITIONS = list_supported_competitions()


def _canonical_hidden_competitions(values: list[str]) -> list[str]:
    hidden = {value for value in values if value in SUPPORTED_COMPETITIONS}
    return [competition for competition in SUPPORTED_COMPETITIONS if competition in hidden]


@router.get("", response_model=CompetitionVisibilityOut)
def get_competition_visibility(
    current_user: User = Depends(get_current_user),
) -> CompetitionVisibilityOut:
    return CompetitionVisibilityOut(
        hidden_competitions=_canonical_hidden_competitions(current_user.hidden_competitions)
    )


@router.put("", response_model=CompetitionVisibilityOut)
def update_competition_visibility(
    payload: UpdateCompetitionVisibilityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompetitionVisibilityOut:
    try:
        normalized = [normalize_competition(value) for value in payload.hidden_competitions]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    current_user.hidden_competitions = _canonical_hidden_competitions(normalized)
    db.commit()
    db.refresh(current_user)
    return CompetitionVisibilityOut(hidden_competitions=current_user.hidden_competitions)
