from typing import Dict, List, Set, Any
import json
import logging
from fastapi import WebSocket
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, ConversationParticipant

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Maps conversation_id -> list of (user_id, WebSocket)
        self.conversation_rooms: Dict[int, List[Dict[str, Any]]] = {}
        # Maps user_id -> set of active WebSockets across all their tabs/rooms
        self.user_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: int, user_id: int):
        await websocket.accept()

        # Add to room
        if conversation_id not in self.conversation_rooms:
            self.conversation_rooms[conversation_id] = []
        self.conversation_rooms[conversation_id].append({
            "user_id": user_id,
            "websocket": websocket
        })

        # Track active user sockets
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
            # User transitioned from offline to online
            await self._set_user_online_status(user_id, is_online=True)
            await self.broadcast_user_status(user_id, is_online=True)

        self.user_connections[user_id].add(websocket)

    async def disconnect(self, websocket: WebSocket, conversation_id: int, user_id: int):
        # Remove from room
        if conversation_id in self.conversation_rooms:
            self.conversation_rooms[conversation_id] = [
                conn for conn in self.conversation_rooms[conversation_id]
                if conn["websocket"] != websocket
            ]
            if not self.conversation_rooms[conversation_id]:
                del self.conversation_rooms[conversation_id]

        # Remove from user connections
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                # User went completely offline
                await self._set_user_online_status(user_id, is_online=False)
                await self.broadcast_user_status(user_id, is_online=False)

    async def broadcast_to_conversation(self, conversation_id: int, data: Dict[str, Any]):
        """Send message payload to all active websockets in this conversation room."""
        if conversation_id in self.conversation_rooms:
            message_text = json.dumps(data)
            dead_connections = []
            for conn in self.conversation_rooms[conversation_id]:
                ws: WebSocket = conn["websocket"]
                try:
                    await ws.send_text(message_text)
                except Exception as e:
                    logger.warning(f"Error broadcasting to ws: {e}")
                    dead_connections.append(conn)

            # Clean up dead sockets
            for dead in dead_connections:
                if dead in self.conversation_rooms.get(conversation_id, []):
                    self.conversation_rooms[conversation_id].remove(dead)

    async def broadcast_to_user(self, user_id: int, data: Dict[str, Any]):
        """Send data to all active websockets belonging to a user."""
        if user_id in self.user_connections:
            message_text = json.dumps(data)
            dead_sockets = set()
            for ws in self.user_connections[user_id]:
                try:
                    await ws.send_text(message_text)
                except Exception:
                    dead_sockets.add(ws)
            for dead in dead_sockets:
                self.user_connections[user_id].discard(dead)

    async def broadcast_user_status(self, user_id: int, is_online: bool):
        """Broadcast user online/offline status change to participants in their conversations."""
        db: Session = SessionLocal()
        try:
            # Find all conversations this user participates in
            user_convs = db.query(ConversationParticipant.conversation_id).filter(
                ConversationParticipant.user_id == user_id
            ).all()
            conv_ids = [c[0] for c in user_convs]

            # Find all partner user IDs
            partner_ids = db.query(ConversationParticipant.user_id).filter(
                ConversationParticipant.conversation_id.in_(conv_ids),
                ConversationParticipant.user_id != user_id
            ).distinct().all()

            status_payload = {
                "type": "user_status",
                "user_id": user_id,
                "is_online": is_online
            }

            for partner in partner_ids:
                p_id = partner[0]
                await self.broadcast_to_user(p_id, status_payload)
        except Exception as e:
            logger.error(f"Error broadcasting user status: {e}")
        finally:
            db.close()

    async def _set_user_online_status(self, user_id: int, is_online: bool):
        """Update is_online column in database."""
        db: Session = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.is_online = is_online
                db.commit()
        except Exception as e:
            logger.error(f"Error updating user online status: {e}")
            db.rollback()
        finally:
            db.close()

    def is_user_online(self, user_id: int) -> bool:
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0


manager = ConnectionManager()
