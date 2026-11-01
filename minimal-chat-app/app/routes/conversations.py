from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models import User, Conversation, ConversationParticipant, Message
from app.schemas import (
    ConversationCreate,
    ConversationResponse,
    UserSearchResponse,
    MessageResponse
)
from app.auth import get_current_user
from app.websocket.manager import manager

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationResponse])
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all conversations the current user participates in."""
    # Find all conversation IDs where current_user is a participant
    user_conv_ids = [
        cp.conversation_id
        for cp in db.query(ConversationParticipant.conversation_id).filter(
            ConversationParticipant.user_id == current_user.id
        ).all()
    ]

    if not user_conv_ids:
        return []

    conversations = (
        db.query(Conversation)
        .filter(Conversation.id.in_(user_conv_ids))
        .all()
    )

    results = []
    for conv in conversations:
        # Find the other participant in this 1-to-1 conversation
        other_participant_record = (
            db.query(ConversationParticipant)
            .filter(
                ConversationParticipant.conversation_id == conv.id,
                ConversationParticipant.user_id != current_user.id
            )
            .first()
        )

        if not other_participant_record or not other_participant_record.user:
            continue

        other_user = other_participant_record.user

        # Get the latest message in this conversation
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(desc(Message.created_at))
            .first()
        )

        last_msg_resp = None
        if last_msg:
            last_msg_resp = MessageResponse(
                id=last_msg.id,
                conversation_id=last_msg.conversation_id,
                sender_id=last_msg.sender_id,
                sender_username=last_msg.sender.username if last_msg.sender else "Unknown",
                sender_profile_picture=last_msg.sender.profile_picture if last_msg.sender else "",
                content=last_msg.content,
                message_type=last_msg.message_type,
                link_preview=last_msg.link_preview,
                created_at=last_msg.created_at,
                is_read=last_msg.is_read
            )

        # Count unread messages sent to current_user
        unread_count = (
            db.query(func.count(Message.id))
            .filter(
                Message.conversation_id == conv.id,
                Message.sender_id != current_user.id,
                Message.is_read == False
            )
            .scalar() or 0
        )

        # Check real-time online status
        is_online = manager.is_user_online(other_user.id) or other_user.is_online

        other_user_resp = UserSearchResponse(
            id=other_user.id,
            username=other_user.username,
            profile_picture=other_user.profile_picture or "",
            is_online=is_online
        )

        results.append(
            ConversationResponse(
                id=conv.id,
                created_at=conv.created_at,
                other_user=other_user_resp,
                last_message=last_msg_resp,
                unread_count=unread_count
            )
        )

    # Sort conversations by last message timestamp (or conversation creation time)
    results.sort(
        key=lambda c: (
            c.last_message.created_at if c.last_message else c.created_at
        ),
        reverse=True
    )

    return results


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_or_get_conversation(
    conv_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start or retrieve an existing private 1-on-1 conversation with another user."""
    recipient_id = conv_data.recipient_user_id
    if recipient_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start a private conversation with yourself."
        )

    recipient = db.query(User).filter(User.id == recipient_id).first()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient user not found."
        )

    # Check if a 1-to-1 conversation already exists between these two users
    current_user_conv_ids = [
        cp.conversation_id for cp in db.query(ConversationParticipant.conversation_id).filter(
            ConversationParticipant.user_id == current_user.id
        ).all()
    ]

    existing_conv_id = None
    if current_user_conv_ids:
        existing_conv_id = (
            db.query(ConversationParticipant.conversation_id)
            .filter(
                ConversationParticipant.user_id == recipient_id,
                ConversationParticipant.conversation_id.in_(current_user_conv_ids)
            )
            .first()
        )

    if existing_conv_id:
        conv = db.query(Conversation).filter(Conversation.id == existing_conv_id[0]).first()
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(desc(Message.created_at))
            .first()
        )
        last_msg_resp = None
        if last_msg:
            last_msg_resp = MessageResponse(
                id=last_msg.id,
                conversation_id=last_msg.conversation_id,
                sender_id=last_msg.sender_id,
                sender_username=last_msg.sender.username if last_msg.sender else "Unknown",
                sender_profile_picture=last_msg.sender.profile_picture if last_msg.sender else "",
                content=last_msg.content,
                message_type=last_msg.message_type,
                link_preview=last_msg.link_preview,
                created_at=last_msg.created_at,
                is_read=last_msg.is_read
            )

        is_online = manager.is_user_online(recipient.id) or recipient.is_online
        return ConversationResponse(
            id=conv.id,
            created_at=conv.created_at,
            other_user=UserSearchResponse(
                id=recipient.id,
                username=recipient.username,
                profile_picture=recipient.profile_picture or "",
                is_online=is_online
            ),
            last_message=last_msg_resp,
            unread_count=0
        )

    # Create new conversation
    new_conv = Conversation()
    db.add(new_conv)
    db.flush()

    p1 = ConversationParticipant(conversation_id=new_conv.id, user_id=current_user.id)
    p2 = ConversationParticipant(conversation_id=new_conv.id, user_id=recipient.id)
    db.add_all([p1, p2])
    db.commit()
    db.refresh(new_conv)

    is_online = manager.is_user_online(recipient.id) or recipient.is_online

    return ConversationResponse(
        id=new_conv.id,
        created_at=new_conv.created_at,
        other_user=UserSearchResponse(
            id=recipient.id,
            username=recipient.username,
            profile_picture=recipient.profile_picture or "",
            is_online=is_online
        ),
        last_message=None,
        unread_count=0
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation_by_id(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve details for a single conversation if user is a participant."""
    part = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == current_user.id
    ).first()

    if not part:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this conversation."
        )

    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    other_part = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id != current_user.id
    ).first()

    if not other_part or not other_part.user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat partner not found.")

    other_user = other_part.user
    is_online = manager.is_user_online(other_user.id) or other_user.is_online

    last_msg = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(desc(Message.created_at))
        .first()
    )
    last_msg_resp = None
    if last_msg:
        last_msg_resp = MessageResponse(
            id=last_msg.id,
            conversation_id=last_msg.conversation_id,
            sender_id=last_msg.sender_id,
            sender_username=last_msg.sender.username if last_msg.sender else "Unknown",
            sender_profile_picture=last_msg.sender.profile_picture if last_msg.sender else "",
            content=last_msg.content,
            message_type=last_msg.message_type,
            link_preview=last_msg.link_preview,
            created_at=last_msg.created_at,
            is_read=last_msg.is_read
        )

    return ConversationResponse(
        id=conv.id,
        created_at=conv.created_at,
        other_user=UserSearchResponse(
            id=other_user.id,
            username=other_user.username,
            profile_picture=other_user.profile_picture or "",
            is_online=is_online
        ),
        last_message=last_msg_resp,
        unread_count=0
    )
