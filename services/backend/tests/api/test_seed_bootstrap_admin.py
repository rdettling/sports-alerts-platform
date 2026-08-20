from app.config import settings
from app.db.models import Team, User
from app.db.session import SessionLocal
from app.services.competitions import competition_teams_query


def test_startup_bootstraps_admin_user(client):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == settings.bootstrap_admin_email).one_or_none()
        assert user is not None
        assert user.role == "admin"
        mlb_team = db.scalar(competition_teams_query("MLB").where(Team.abbreviation == "LAD"))
        assert mlb_team is not None
