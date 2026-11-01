def test_register_user_success(client):
    response = client.post(
        "/api/register",
        json={
            "username": "alex",
            "email": "alex@example.com",
            "password": "secretpassword123",
            "profile_picture": "https://example.com/alex.png"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["username"] == "alex"
    assert data["user"]["email"] == "alex@example.com"


def test_register_duplicate_username(client):
    client.post(
        "/api/register",
        json={"username": "sarah", "email": "sarah1@example.com", "password": "password123"}
    )
    # Attempt second registration with same username
    response = client.post(
        "/api/register",
        json={"username": "sarah", "email": "sarah2@example.com", "password": "password123"}
    )
    assert response.status_code == 400
    assert "Username is already taken" in response.json()["detail"]


def test_login_success(client):
    client.post(
        "/api/register",
        json={"username": "johndoe", "email": "john@example.com", "password": "securepassword"}
    )
    login_resp = client.post(
        "/api/login",
        json={"username": "johndoe", "password": "securepassword"}
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["user"]["username"] == "johndoe"


def test_login_invalid_password(client):
    client.post(
        "/api/register",
        json={"username": "charlie", "email": "charlie@example.com", "password": "mypassword"}
    )
    bad_login = client.post(
        "/api/login",
        json={"username": "charlie", "password": "wrongpassword"}
    )
    assert bad_login.status_code == 401
    assert "Incorrect username or password" in bad_login.json()["detail"]


def test_get_current_user_profile(client):
    reg = client.post(
        "/api/register",
        json={"username": "emma", "email": "emma@example.com", "password": "emmapassword"}
    )
    token = reg.json()["access_token"]
    profile_resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert profile_resp.status_code == 200
    assert profile_resp.json()["username"] == "emma"
