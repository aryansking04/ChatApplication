def test_create_and_list_conversations(client):
    # Register user 1
    r1 = client.post("/api/register", json={"username": "user1", "email": "u1@test.com", "password": "password123"})
    token1 = r1.json()["access_token"]
    u1_id = r1.json()["user"]["id"]

    # Register user 2
    r2 = client.post("/api/register", json={"username": "user2", "email": "u2@test.com", "password": "password123"})
    token2 = r2.json()["access_token"]
    u2_id = r2.json()["user"]["id"]

    # Register user 3 (stranger)
    r3 = client.post("/api/register", json={"username": "user3", "email": "u3@test.com", "password": "password123"})
    token3 = r3.json()["access_token"]

    # User 1 searches for user 2
    search_resp = client.get("/api/users/search?q=user2", headers={"Authorization": f"Bearer {token1}"})
    assert search_resp.status_code == 200
    assert len(search_resp.json()) == 1
    assert search_resp.json()[0]["username"] == "user2"

    # User 1 creates conversation with User 2
    conv_resp = client.post(
        "/api/conversations",
        json={"recipient_user_id": u2_id},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # Repeating creation returns the same conversation without duplication
    dup_resp = client.post(
        "/api/conversations",
        json={"recipient_user_id": u2_id},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert dup_resp.status_code == 201 or dup_resp.status_code == 200
    assert dup_resp.json()["id"] == conv_id

    # User 1 lists conversations
    list1 = client.get("/api/conversations", headers={"Authorization": f"Bearer {token1}"})
    assert list1.status_code == 200
    assert len(list1.json()) == 1
    assert list1.json()[0]["other_user"]["username"] == "user2"

    # User 2 lists conversations (should also see User 1)
    list2 = client.get("/api/conversations", headers={"Authorization": f"Bearer {token2}"})
    assert list2.status_code == 200
    assert len(list2.json()) == 1
    assert list2.json()[0]["other_user"]["username"] == "user1"

    # Stranger (user 3) tries to get conversation by ID -> 403 Forbidden
    forbidden_resp = client.get(f"/api/conversations/{conv_id}", headers={"Authorization": f"Bearer {token3}"})
    assert forbidden_resp.status_code == 403


def test_cannot_chat_with_self(client):
    r = client.post("/api/register", json={"username": "lonely", "email": "lonely@test.com", "password": "password123"})
    token = r.json()["access_token"]
    u_id = r.json()["user"]["id"]

    res = client.post(
        "/api/conversations",
        json={"recipient_user_id": u_id},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "Cannot start a private conversation with yourself" in res.json()["detail"]
