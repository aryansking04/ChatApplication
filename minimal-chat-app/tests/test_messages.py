def test_send_and_receive_messages(client):
    # Setup two users and a conversation
    r1 = client.post("/api/register", json={"username": "alice", "email": "alice@test.com", "password": "password123"})
    token1 = r1.json()["access_token"]
    u1_id = r1.json()["user"]["id"]

    r2 = client.post("/api/register", json={"username": "bob", "email": "bob@test.com", "password": "password123"})
    token2 = r2.json()["access_token"]
    u2_id = r2.json()["user"]["id"]

    conv = client.post("/api/conversations", json={"recipient_user_id": u2_id}, headers={"Authorization": f"Bearer {token1}"})
    conv_id = conv.json()["id"]

    # 1. Alice sends a text message
    m1 = client.post(
        "/api/messages",
        json={"conversation_id": conv_id, "content": "Hello Bob!"},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert m1.status_code == 201
    assert m1.json()["content"] == "Hello Bob!"
    assert m1.json()["message_type"] == "text"
    assert m1.json()["is_read"] is False

    # 2. Bob sends an Instagram Reel link
    m2 = client.post(
        "/api/messages",
        json={"conversation_id": conv_id, "content": "Look at this reel: https://www.instagram.com/reel/C21AbCdEfGh/"},
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert m2.status_code == 201
    m2_data = m2.json()
    assert m2_data["message_type"] == "instagram_reel"
    assert m2_data["link_preview"] is not None
    assert m2_data["link_preview"]["platform"] == "instagram"
    assert m2_data["link_preview"]["media_id"] == "C21AbCdEfGh"

    # 3. Bob sends a YouTube link
    m3 = client.post(
        "/api/messages",
        json={"conversation_id": conv_id, "content": "Also this video https://youtu.be/dQw4w9WgXcQ"},
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert m3.status_code == 201
    assert m3.json()["message_type"] == "youtube"
    assert m3.json()["link_preview"]["platform"] == "youtube"

    # 4. Alice fetches message history
    history = client.get(f"/api/messages/{conv_id}", headers={"Authorization": f"Bearer {token1}"})
    assert history.status_code == 200
    msg_list = history.json()
    assert len(msg_list) == 3

    # Alice fetching history marks Bob's messages as read
    assert msg_list[1]["is_read"] is True


def test_unauthorized_user_cannot_access_messages(client):
    r1 = client.post("/api/register", json={"username": "user_a", "email": "a@test.com", "password": "password123"})
    token1 = r1.json()["access_token"]
    u1_id = r1.json()["user"]["id"]

    r2 = client.post("/api/register", json={"username": "user_b", "email": "b@test.com", "password": "password123"})
    token2 = r2.json()["access_token"]
    u2_id = r2.json()["user"]["id"]

    r3 = client.post("/api/register", json={"username": "hacker", "email": "h@test.com", "password": "password123"})
    token3 = r3.json()["access_token"]

    conv = client.post("/api/conversations", json={"recipient_user_id": u2_id}, headers={"Authorization": f"Bearer {token1}"})
    conv_id = conv.json()["id"]

    # Hacker attempts to read messages
    res_get = client.get(f"/api/messages/{conv_id}", headers={"Authorization": f"Bearer {token3}"})
    assert res_get.status_code == 403

    # Hacker attempts to send message
    res_post = client.post(
        "/api/messages",
        json={"conversation_id": conv_id, "content": "I am eavesdropping"},
        headers={"Authorization": f"Bearer {token3}"}
    )
    assert res_post.status_code == 403
