from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import User
from app.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserSearchResponse,
    TokenResponse
)
from app.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api", tags=["Users & Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, response: Response, db: Session = Depends(get_db)):
    """Register a new user account with a unique username and email."""
    # Check if username or email already exists
    existing_user = db.query(User).filter(
        or_(User.username == user_data.username.lower(), User.email == user_data.email.lower())
    ).first()

    if existing_user:
        if existing_user.username.lower() == user_data.username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken. Please choose another."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered. Please log in."
            )

    # Clean profile picture or set default avatar initials SVG/dicebear/minimal
    profile_pic = user_data.profile_picture.strip() if user_data.profile_picture else ""
    if not profile_pic:
        # Generate an ultra-clean initials or svg avatar URL
        profile_pic = f"https://api.dicebear.com/7.x/initials/svg?seed={user_data.username}&backgroundColor=f1f5f9&textColor=0f172a"

    new_user = User(
        username=user_data.username.lower(),
        email=user_data.email.lower(),
        hashed_password=get_password_hash(user_data.password),
        profile_picture=profile_pic,
        is_online=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(data={"sub": str(new_user.id), "username": new_user.username})

    # Set HTTP-only cookie for secure browser navigation
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=30 * 24 * 3600,
        samesite="lax",
        secure=False  # Set True in production over HTTPS
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLogin, response: Response, db: Session = Depends(get_db)):
    """Authenticate a user and return access token."""
    username_or_email = login_data.username.strip().lower()
    user = db.query(User).filter(
        or_(User.username == username_or_email, User.email == username_or_email)
    ).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id), "username": user.username})

    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=30 * 24 * 3600,
        samesite="lax",
        secure=False
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.post("/logout")
def logout(response: Response, current_user: User = Depends(get_current_user)):
    """Log out current user by clearing cookies."""
    response.delete_cookie("access_token")
    return {"message": "Successfully logged out"}


@router.get("/users/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get profile of current logged-in user."""
    return UserResponse.model_validate(current_user)


@router.get("/users/search", response_model=List[UserSearchResponse])
def search_users(
    q: Optional[str] = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search for other users by username for 1-on-1 chatting."""
    query = q.strip().lower() if q else ""
    base_query = db.query(User).filter(User.id != current_user.id)
    if query:
        base_query = base_query.filter(User.username.like(f"%{query}%"))
    
    users = base_query.limit(25).all()
    return [UserSearchResponse.model_validate(u) for u in users]
