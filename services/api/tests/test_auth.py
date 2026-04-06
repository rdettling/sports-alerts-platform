def test_register_login_me_flow(client):
    register_response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert register_response.status_code == 201
    register_data = register_response.json()
    assert "access_token" in register_data
    assert register_data["user"]["email"] == "user@example.com"

    login_response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


def test_login_fails_with_invalid_credentials(client):
    client.post("/auth/register", json={"email": "other@example.com", "password": "password123"})
    response = client.post("/auth/login", json={"email": "other@example.com", "password": "wrongpassword"})
    assert response.status_code == 401


def test_register_conflict_on_existing_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
