from typing import List, Optional, Dict, Any
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import User, Conversation, ConversationParticipant, Message
from app.schemas import MessageCreate, MessageResponse
from app.auth import get_current_user, get_user_from_token_string
from app.services.link_preview import extract_and_generate_preview, get_general_url_metadata
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Messages & Real-time"])


@router.get("/api/messages/{conversation_id}", response_model=List[MessageResponse])
def get_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve message history for a conversation. Marks partner messages as read."""
    # Ensure current user is a participant
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == current_user.id
    ).first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view messages in this conversation."
        )

    # Fetch all messages in chronological order
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    # Mark unread messages sent by the other user as read
    unread_messages = [m for m in messages if m.sender_id != current_user.id and not m.is_read]
    if unread_messages:
        for m in unread_messages:
            m.is_read = True
        db.commit()

    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            sender_id=m.sender_id,
            sender_username=m.sender.username if m.sender else "Unknown",
            sender_profile_picture=m.sender.profile_picture if m.sender else "",
            content=m.content,
            message_type=m.message_type,
            link_preview=m.link_preview,
            created_at=m.created_at,
            is_read=m.is_read
        )
        for m in messages
    ]


@router.post("/api/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message_api(
    msg_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """REST endpoint to send a message."""
    # Validate participant
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == msg_data.conversation_id,
        ConversationParticipant.user_id == current_user.id
    ).first()

    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this conversation."
        )

    content = msg_data.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty."
        )

    # Detect URLs and build preview
    msg_type, preview_meta = extract_and_generate_preview(content)

    new_msg = Message(
        conversation_id=msg_data.conversation_id,
        sender_id=current_user.id,
        content=content,
        message_type=msg_type,
        link_preview=preview_meta,
        created_at=datetime.now(timezone.utc),
        is_read=False
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    response_payload = MessageResponse(
        id=new_msg.id,
        conversation_id=new_msg.conversation_id,
        sender_id=new_msg.sender_id,
        sender_username=current_user.username,
        sender_profile_picture=current_user.profile_picture or "",
        content=new_msg.content,
        message_type=new_msg.message_type,
        link_preview=new_msg.link_preview,
        created_at=new_msg.created_at,
        is_read=new_msg.is_read
    )

    # Broadcast to WebSocket room
    broadcast_data = {
        "type": "new_message",
        "message": response_payload.model_dump(mode="json")
    }
    await manager.broadcast_to_conversation(msg_data.conversation_id, broadcast_data)

    # Also notify recipient for their conversation sidebar
    recipient_part = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == msg_data.conversation_id,
        ConversationParticipant.user_id != current_user.id
    ).first()
    if recipient_part:
        await manager.broadcast_to_user(recipient_part.user_id, {
            "type": "sidebar_update",
            "conversation_id": msg_data.conversation_id,
            "last_message": response_payload.model_dump(mode="json"),
            "sender_username": current_user.username
        })

    return response_payload


@router.post("/api/messages/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all unread messages in conversation as read and notify sender."""
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == current_user.id
    ).first()

    if not participant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    unread = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user.id,
            Message.is_read == False
        )
        .all()
    )

    if unread:
        for m in unread:
            m.is_read = True
        db.commit()

        # Broadcast read receipt to room
        await manager.broadcast_to_conversation(conversation_id, {
            "type": "messages_read",
            "conversation_id": conversation_id,
            "reader_id": current_user.id
        })

    return {"status": "ok", "marked_read_count": len(unread)}


@router.get("/api/preview")
def preview_link(url: str, current_user: User = Depends(get_current_user)):
    """Helper preview endpoint for clients wishing to preview a URL."""
    msg_type, meta = extract_and_generate_preview(url)
    return {"message_type": msg_type, "preview": meta}


@router.websocket("/ws/{conversation_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    conversation_id: int,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Authenticated WebSocket endpoint for real-time messaging, typing indicators,
    and presence detection in a conversation.
    """
    # 1. Authenticate user from query token or cookie
    auth_token = token
    if not auth_token:
        cookie_token = websocket.cookies.get("access_token")
        if cookie_token:
            auth_token = cookie_token.replace("Bearer ", "").strip()

    if not auth_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = get_user_from_token_string(auth_token, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Check authorization: is user a participant in this conversation?
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == user.id
    ).first()

    if not participant:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = user.id
    username = user.username
    user_pic = user.profile_picture or ""

    # 3. Connect to room
    await manager.connect(websocket, conversation_id, user_id)

    try:
        while True:
            raw_text = await websocket.receive_text()
            if not raw_text:
                continue

            try:
                data = json.loads(raw_text)
            except Exception:
                continue

            event_type = data.get("type")

            # A. New chat message
            if event_type == "message":
                content = data.get("content", "").strip()
                if not content:
                    continue

                # Run URL detection & preview metadata extraction
                msg_type, preview_meta = extract_and_generate_preview(content)

                # Persist message to SQLite
                new_msg = Message(
                    conversation_id=conversation_id,
                    sender_id=user_id,
                    content=content,
                    message_type=msg_type,
                    link_preview=preview_meta,
                    created_at=datetime.now(timezone.utc),
                    is_read=False
                )
                db.add(new_msg)
                db.commit()
                db.refresh(new_msg)

                msg_dict = {
                    "id": new_msg.id,
                    "conversation_id": new_msg.conversation_id,
                    "sender_id": new_msg.sender_id,
                    "sender_username": username,
                    "sender_profile_picture": user_pic,
                    "content": new_msg.content,
                    "message_type": new_msg.message_type,
                    "link_preview": new_msg.link_preview,
                    "created_at": new_msg.created_at.isoformat(),
                    "is_read": False
                }

                # Broadcast to conversation room
                await manager.broadcast_to_conversation(conversation_id, {
                    "type": "new_message",
                    "message": msg_dict
                })

                # Broadcast sidebar update to the partner
                partner_part = db.query(ConversationParticipant).filter(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.user_id != user_id
                ).first()
                if partner_part:
                    await manager.broadcast_to_user(partner_part.user_id, {
                        "type": "sidebar_update",
                        "conversation_id": conversation_id,
                        "last_message": msg_dict,
                        "sender_username": username
                    })

            # B. Typing indicator
            elif event_type == "typing":
                is_typing = bool(data.get("is_typing", False))
                await manager.broadcast_to_conversation(conversation_id, {
                    "type": "typing",
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "username": username,
                    "is_typing": is_typing
                })

            # C. Read receipt
            elif event_type == "mark_read":
                unread_items = (
                    db.query(Message)
                    .filter(
                        Message.conversation_id == conversation_id,
                        Message.sender_id != user_id,
                        Message.is_read == False
                    )
                    .all()
                )
                if unread_items:
                    for item in unread_items:
                        item.is_read = True
                    db.commit()

                await manager.broadcast_to_conversation(conversation_id, {
                    "type": "messages_read",
                    "conversation_id": conversation_id,
                    "reader_id": user_id
                })

    except WebSocketDisconnect:
        await manager.disconnect(websocket, conversation_id, user_id)
    except Exception as e:
        logger.error(f"WebSocket error in conversation {conversation_id}: {e}")
        await manager.disconnect(websocket, conversation_id, user_id)
