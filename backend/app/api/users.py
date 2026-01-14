"""User API routes"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, TrackedToken, UserAlert

router = APIRouter()


class UserProfileResponse(BaseModel):
    id: str
    email: str
    username: Optional[str]
    display_name: Optional[str]
    subscription_tier: str
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None


class TrackTokenRequest(BaseModel):
    token_address: str
    chain: str
    alert_on_mention: bool = True
    alert_on_price_change: float = 0.2
    notes: Optional[str] = None


class TrackedTokenResponse(BaseModel):
    id: str
    token_address: str
    chain: str
    alert_on_mention: bool
    alert_on_price_change: float
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: str
    alert_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    token_address: Optional[str]

    class Config:
        from_attributes = True


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current user profile"""
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile"""
    if request.username:
        # Check if username is taken
        result = await db.execute(
            select(User).where(
                User.username == request.username,
                User.id != current_user.id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )
        current_user.username = request.username
    
    if request.display_name is not None:
        current_user.display_name = request.display_name
    
    return current_user


@router.get("/me/tracked-tokens", response_model=List[TrackedTokenResponse])
async def get_tracked_tokens(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's tracked tokens"""
    result = await db.execute(
        select(TrackedToken).where(TrackedToken.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/me/tracked-tokens", response_model=TrackedTokenResponse)
async def track_token(
    request: TrackTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Track a token"""
    # Check if already tracking
    result = await db.execute(
        select(TrackedToken).where(
            TrackedToken.user_id == current_user.id,
            TrackedToken.token_address == request.token_address,
            TrackedToken.chain == request.chain,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token already tracked",
        )
    
    tracked = TrackedToken(
        user_id=current_user.id,
        token_address=request.token_address,
        chain=request.chain,
        alert_on_mention=request.alert_on_mention,
        alert_on_price_change=request.alert_on_price_change,
        notes=request.notes,
    )
    db.add(tracked)
    await db.flush()
    
    return tracked


@router.delete("/me/tracked-tokens/{token_id}")
async def untrack_token(
    token_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop tracking a token"""
    result = await db.execute(
        select(TrackedToken).where(
            TrackedToken.id == token_id,
            TrackedToken.user_id == current_user.id,
        )
    )
    tracked = result.scalar_one_or_none()
    
    if not tracked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracked token not found",
        )
    
    await db.delete(tracked)
    return {"status": "ok"}


@router.get("/me/alerts", response_model=List[AlertResponse])
async def get_alerts(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's alerts"""
    query = select(UserAlert).where(UserAlert.user_id == current_user.id)
    
    if unread_only:
        query = query.where(UserAlert.is_read == False)
    
    query = query.order_by(UserAlert.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/me/alerts/{alert_id}/read")
async def mark_alert_read(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark alert as read"""
    result = await db.execute(
        select(UserAlert).where(
            UserAlert.id == alert_id,
            UserAlert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )
    
    alert.is_read = True
    alert.read_at = datetime.utcnow()
    
    return {"status": "ok"}
