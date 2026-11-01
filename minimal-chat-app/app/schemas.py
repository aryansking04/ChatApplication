from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


# --- User Schemas ---

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)
    profile_picture: Optional[str] = ""

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not v.isalnum() and "_" not in v and "-" not in v:
            raise ValueError("Username can only contain alphanumeric characters, underscores, and dashes.")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    profile_picture: Optional[str] = ""
    is_online: bool
    created_at: datetime


class UserSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    profile_picture: Optional[str] = ""
    is_online: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Link Preview Schema ---

class LinkPreviewData(BaseModel):
    platform: str  # instagram, youtube, general, none
    original_url: str
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    site_name: Optional[str] = None
    media_id: Optional[str] = None  # e.g., YouTube video ID or Instagram reel shortcode
    is_reel: Optional[bool] = False


# --- Message Schemas ---

class MessageCreate(BaseModel):
    conversation_id: int
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int
    sender_username: Optional[str] = None
    sender_profile_picture: Optional[str] = None
    content: str
    message_type: str
    link_preview: Optional[Dict[str, Any]] = None
    created_at: datetime
    is_read: bool


# --- Conversation Schemas ---

class ConversationCreate(BaseModel):
    recipient_user_id: int


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    other_user: UserSearchResponse
    last_message: Optional[MessageResponse] = None
    unread_count: int = 0


class TypingPayload(BaseModel):
    conversation_id: int
    is_typing: bool

