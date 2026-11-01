from datetime import datetime, timezone
import json
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    profile_picture = Column(String(255), nullable=True, default="")
    is_online = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    participations = relationship("ConversationParticipant", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    participants = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_conv_user"),
        Index("idx_participant_lookup", "conversation_id", "user_id"),
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="participants")
    user = relationship("User", back_populates="participations")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sender_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    content = Column(Text, nullable=False)
    message_type = Column(String(30), default="text", nullable=False)  # text, instagram_reel, youtube, link
    link_preview_raw = Column(Text, nullable=True)  # JSON-encoded preview metadata
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    is_read = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_conv_created", "conversation_id", "created_at"),
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="messages")

    @property
    def link_preview(self):
        if self.link_preview_raw:
            try:
                return json.loads(self.link_preview_raw)
            except Exception:
                return None
        return None

    @link_preview.setter
    def link_preview(self, value):
        if value is not None:
            self.link_preview_raw = json.dumps(value)
        else:
            self.link_preview_raw = None
