from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import User
from app.db.session import SessionLocal


def _auth_headers(email: str) -> tuple[dict[str, str], int]:
    with SessionLocal() as db:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}, user.id


def test_competition_visibility_requires_authentication(client):
    assert client.get("/competition-visibility").status_code == 403
    assert (
        client.put(
            "/competition-visibility",
            json={"hidden_competitions": ["NBA"]},
        ).status_code
        == 403
    )


def test_competition_visibility_defaults_to_all_visible(client):
    headers, _ = _auth_headers("visibility-default@example.com")

    response = client.get("/competition-visibility", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"hidden_competitions": []}


def test_competition_visibility_replaces_and_canonicalizes_selection(client):
    headers, user_id = _auth_headers("visibility-update@example.com")

    response = client.put(
        "/competition-visibility",
        headers=headers,
        json={"hidden_competitions": ["world_cup", "NBA", "WORLD_CUP", "fbs"]},
    )

    assert response.status_code == 200
    assert response.json() == {"hidden_competitions": ["NBA", "FBS", "WORLD_CUP"]}
    assert client.get("/competition-visibility", headers=headers).json() == response.json()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.id == user_id))
        assert user is not None
        assert user.hidden_competitions == ["NBA", "FBS", "WORLD_CUP"]


def test_competition_visibility_is_scoped_to_current_user(client):
    first_headers, _ = _auth_headers("visibility-first@example.com")
    second_headers, _ = _auth_headers("visibility-second@example.com")
    client.put(
        "/competition-visibility",
        headers=first_headers,
        json={"hidden_competitions": ["MLB"]},
    )

    assert client.get("/competition-visibility", headers=first_headers).json() == {
        "hidden_competitions": ["MLB"]
    }
    assert client.get("/competition-visibility", headers=second_headers).json() == {
        "hidden_competitions": []
    }


def test_competition_visibility_rejects_unknown_competitions(client):
    headers, _ = _auth_headers("visibility-invalid@example.com")

    response = client.put(
        "/competition-visibility",
        headers=headers,
        json={"hidden_competitions": ["NBA", "NOT_A_LEAGUE"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported competition: NOT_A_LEAGUE"
    assert client.get("/competition-visibility", headers=headers).json() == {
        "hidden_competitions": []
    }
