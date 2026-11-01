import pytest
from app.auth import create_access_token


def test_websocket_chat_flow(client):
    # 1. Create two users and conversation
    u1_reg = client.post("/api/register", json={"username": "ws_user1", "email": "ws1@test.com", "password": "password123"})
    token1 = u1_reg.json()["access_token"]
    u1_id = u1_reg.json()["user"]["id"]

    u2_reg = client.post("/api/register", json={"username": "ws_user2", "email": "ws2@test.com", "password": "password123"})
    token2 = u2_reg.json()["access_token"]
    u2_id = u2_reg.json()["user"]["id"]

    conv = client.post("/api/conversations", json={"recipient_user_id": u2_id}, headers={"Authorization": f"Bearer {token1}"})
    conv_id = conv.json()["id"]

    # 2. Clear cookies and test WebSocket connection without token fails
    client.cookies.clear()
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/{conv_id}"):
            pass

    # 3. Test WebSocket connection with invalid token fails
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/{conv_id}?token=invalid.token.here"):
            pass

    # 4. Connect user 1 and user 2 simultaneously to the conversation room
    with client.websocket_connect(f"/ws/{conv_id}?token={token1}") as ws1:
        with client.websocket_connect(f"/ws/{conv_id}?token={token2}") as ws2:
            # User 1 sends typing event
            ws1.send_json({"type": "typing", "is_typing": True})

            # Both ws1 and ws2 receive typing broadcast
            t_echo1 = ws1.receive_json()
            assert t_echo1["type"] == "typing"

            ev = ws2.receive_json()
            assert ev["type"] == "typing"
            assert ev["user_id"] == u1_id
            assert ev["is_typing"] is True

            # User 1 sends a message with an Instagram Reel link
            reel_url = "https://www.instagram.com/reel/C89abcdefgh/"
            ws1.send_json({"type": "message", "content": f"Hey checkout this reel {reel_url}"})

            # User 1 receives echo
            msg_echo1 = ws1.receive_json()
            assert msg_echo1["type"] == "new_message"
            assert msg_echo1["message"]["message_type"] == "instagram_reel"
            assert msg_echo1["message"]["link_preview"]["media_id"] == "C89abcdefgh"

            # User 2 receives real-time broadcast
            msg_ev2 = ws2.receive_json()
            assert msg_ev2["type"] == "new_message"
            assert msg_ev2["message"]["sender_id"] == u1_id
            assert msg_ev2["message"]["message_type"] == "instagram_reel"

            # User 2 marks messages as read
            ws2.send_json({"type": "mark_read"})
            read_ev = ws1.receive_json()
            assert read_ev["type"] == "messages_read"
            assert read_ev["conversation_id"] == conv_id
            assert read_ev["reader_id"] == u2_id
