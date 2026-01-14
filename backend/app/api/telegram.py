"""Telegram API routes"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.telegram import TelegramAccount, TelegramSource
from app.services.telegram.auth import telegram_auth_service, AuthState
from app.services.telegram.session import session_manager
from app.core.security import encrypt_data

router = APIRouter()


class StartAuthRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str


class VerifyCodeRequest(BaseModel):
    code: str


class Verify2FARequest(BaseModel):
    password: str


class AuthStatusResponse(BaseModel):
    state: str
    session_name: str
    message: Optional[str] = None


class AddSourceRequest(BaseModel):
    telegram_id: str
    source_type: str  # group, channel, bot
    name: str
    username: Optional[str] = None
    priority: str = "medium"
    filters: Optional[dict] = None


class SourceResponse(BaseModel):
    id: str
    telegram_id: str
    source_type: str
    name: str
    username: Optional[str]
    priority: str
    is_active: bool
    total_messages: int
    created_at: datetime

    class Config:
        from_attributes = True


class TelegramAccountResponse(BaseModel):
    id: str
    session_name: str
    is_active: bool
    is_connected: bool
    last_connected: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/auth/start", response_model=AuthStatusResponse)
async def start_telegram_auth(
    request: StartAuthRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start Telegram authentication flow"""
    session_name = f"user_{current_user.id}_{datetime.utcnow().timestamp()}"
    
    state, error = await telegram_auth_service.start_auth(
        api_id=request.api_id,
        api_hash=request.api_hash,
        phone=request.phone,
        session_name=session_name,
    )
    
    if state == AuthState.ERROR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Authentication failed",
        )
    
    # Store encrypted credentials temporarily in session
    # Full account creation happens after auth completes
    
    return AuthStatusResponse(
        state=state.value,
        session_name=session_name,
        message="Code sent to your Telegram" if state == AuthState.AWAITING_CODE else None,
    )


@router.post("/auth/verify-code", response_model=AuthStatusResponse)
async def verify_telegram_code(
    session_name: str,
    request: VerifyCodeRequest,
    current_user: User = Depends(get_current_user),
):
    """Verify Telegram authentication code"""
    state, error = await telegram_auth_service.verify_code(
        session_name=session_name,
        code=request.code,
    )
    
    if state == AuthState.ERROR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Verification failed",
        )
    
    return AuthStatusResponse(
        state=state.value,
        session_name=session_name,
        message="2FA required" if state == AuthState.AWAITING_2FA else "Authenticated",
    )


@router.post("/auth/verify-2fa", response_model=AuthStatusResponse)
async def verify_telegram_2fa(
    session_name: str,
    request: Verify2FARequest,
    current_user: User = Depends(get_current_user),
):
    """Verify Telegram 2FA password"""
    state, error = await telegram_auth_service.verify_2fa(
        session_name=session_name,
        password=request.password,
    )
    
    if state == AuthState.ERROR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "2FA verification failed",
        )
    
    return AuthStatusResponse(
        state=state.value,
        session_name=session_name,
        message="Authenticated",
    )


@router.post("/auth/complete", response_model=TelegramAccountResponse)
async def complete_telegram_auth(
    session_name: str,
    api_id: int,
    api_hash: str,
    phone: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete Telegram auth and save account"""
    encrypted_session, user_info = await telegram_auth_service.complete_auth(session_name)
    
    if not encrypted_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication not completed",
        )
    
    # Create account record
    account = TelegramAccount(
        user_id=current_user.id,
        api_id_encrypted=encrypt_data(str(api_id)),
        api_hash_encrypted=encrypt_data(api_hash),
        phone_encrypted=encrypt_data(phone),
        session_string_encrypted=encrypted_session,
        session_name=session_name,
        is_active=True,
        is_connected=True,
        last_connected=datetime.utcnow(),
    )
    db.add(account)
    await db.flush()
    
    return account


@router.post("/auth/cancel")
async def cancel_telegram_auth(
    session_name: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel ongoing Telegram auth"""
    await telegram_auth_service.cancel_auth(session_name)
    return {"status": "ok"}


@router.get("/accounts", response_model=List[TelegramAccountResponse])
async def get_telegram_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's Telegram accounts"""
    result = await db.execute(
        select(TelegramAccount).where(TelegramAccount.user_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/accounts/{account_id}")
async def delete_telegram_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a Telegram account"""
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.id == account_id,
            TelegramAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    
    await db.delete(account)
    return {"status": "ok"}


@router.get("/accounts/{account_id}/sources", response_model=List[SourceResponse])
async def get_account_sources(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get sources for a Telegram account"""
    # Verify account ownership
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.id == account_id,
            TelegramAccount.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    
    result = await db.execute(
        select(TelegramSource).where(TelegramSource.account_id == account_id)
    )
    return result.scalars().all()


@router.post("/accounts/{account_id}/sources", response_model=SourceResponse)
async def add_source(
    account_id: str,
    request: AddSourceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a source to monitor"""
    # Verify account ownership
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.id == account_id,
            TelegramAccount.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    
    # Check if source already exists
    result = await db.execute(
        select(TelegramSource).where(
            TelegramSource.account_id == account_id,
            TelegramSource.telegram_id == request.telegram_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source already added",
        )
    
    source = TelegramSource(
        account_id=account_id,
        telegram_id=request.telegram_id,
        source_type=request.source_type,
        name=request.name,
        username=request.username,
        priority=request.priority,
        filters=request.filters or {},
        is_active=True,
    )
    db.add(source)
    await db.flush()
    
    return source


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a source"""
    # Get source with account check
    result = await db.execute(
        select(TelegramSource).where(TelegramSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    # Verify ownership
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.id == source.account_id,
            TelegramAccount.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    await db.delete(source)
    return {"status": "ok"}


@router.patch("/sources/{source_id}")
async def update_source(
    source_id: str,
    priority: Optional[str] = None,
    is_active: Optional[bool] = None,
    filters: Optional[dict] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a source"""
    # Get and verify source
    result = await db.execute(
        select(TelegramSource).where(TelegramSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    # Verify ownership
    result = await db.execute(
        select(TelegramAccount).where(
            TelegramAccount.id == source.account_id,
            TelegramAccount.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    if priority is not None:
        source.priority = priority
    if is_active is not None:
        source.is_active = is_active
    if filters is not None:
        source.filters = filters
    
    return {"status": "ok"}
