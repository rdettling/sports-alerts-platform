from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal


def test_startup_bootstraps_admin_user(client):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == settings.bootstrap_admin_email).one_or_none()
        assert user is not None
        assert user.role == "admin"
