"""Telegram API routes"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.telegram import TelegramAccount, TelegramSource
from app.services.telegram.auth import telegram_auth_service, AuthState
from app.services.telegram.session import session_manager
from app.core.security import encrypt_data

logger = structlog.get_logger()

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


class DialogResponse(BaseModel):
    id: int
    name: str
    type: str  # channel, group, bot, user
    username: Optional[str] = None
    unread_count: int = 0


@router.get("/accounts/{account_id}/dialogs", response_model=List[DialogResponse])
async def get_account_dialogs(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user's Telegram dialogs (channels, groups, bots).
    Used to browse available sources to add.
    """
    from app.services.telegram.client import telegram_service
    
    # Get account and verify ownership
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
    
    # Connect to Telegram if not already connected
    if account.session_name not in telegram_service._active_clients:
        connected = await telegram_service.connect_account(
            session_name=account.session_name,
            api_id_encrypted=account.api_id_encrypted,
            api_hash_encrypted=account.api_hash_encrypted,
            session_string_encrypted=account.session_string_encrypted,
        )
        if not connected:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to connect to Telegram",
            )
    
    # Get dialogs
    dialogs = await telegram_service.get_dialogs(account.session_name, limit=100)
    
    # Filter to only groups, channels, and bots
    filtered = [
        d for d in dialogs
        if d.get("type") in ("channel", "group", "bot")
    ]
    
    return filtered


class IngestRequest(BaseModel):
    limit: int = 50  # Messages per source


class IngestResponse(BaseModel):
    messages_processed: int
    tokens_found: int
    clusters_updated: int


@router.post("/accounts/{account_id}/ingest", response_model=IngestResponse)
async def ingest_messages(
    account_id: str,
    request: IngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch and process recent messages from all active sources.
    This is a manual trigger for message ingestion.
    
    Now captures CONTEXT around token mentions - the actual discussion,
    not just the scan/bot messages.
    """
    from app.services.telegram.client import telegram_service
    from app.services.extraction.extractor import extraction_service
    from app.services.clustering.cluster_service import clustering_service
    from telethon.tl.types import Channel, Chat
    
    # Get account and verify ownership
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
    
    # Get active sources
    result = await db.execute(
        select(TelegramSource).where(
            TelegramSource.account_id == account_id,
            TelegramSource.is_active == True,
        )
    )
    sources = result.scalars().all()
    
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active sources to ingest from",
        )
    
    # Connect to Telegram if not already connected
    if account.session_name not in telegram_service._active_clients:
        connected = await telegram_service.connect_account(
            session_name=account.session_name,
            api_id_encrypted=account.api_id_encrypted,
            api_hash_encrypted=account.api_hash_encrypted,
            session_string_encrypted=account.session_string_encrypted,
        )
        if not connected:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to connect to Telegram",
            )
    
    client = telegram_service._active_clients.get(account.session_name)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Telegram client not available",
        )
    
    messages_processed = 0
    tokens_found = 0
    clusters_updated = set()
    context_window = 5  # Number of messages before/after to capture as context
    
    # Process each source
    for source in sources:
        try:
            # Get entity
            try:
                entity_id = int(source.telegram_id)
                entity = await client.get_entity(entity_id)
            except ValueError:
                entity = await client.get_entity(source.telegram_id)
            
            # Determine chain based on source name/keywords
            chain = "solana"  # Default
            source_name_lower = source.name.lower()
            if "eth" in source_name_lower or "ethereum" in source_name_lower:
                chain = "ethereum"
            elif "base" in source_name_lower:
                chain = "base"
            elif "bsc" in source_name_lower or "bnb" in source_name_lower:
                chain = "bsc"
            
            # Fetch recent messages
            messages = await client.get_messages(entity, limit=request.limit)
            messages_list = list(messages)  # Convert to list for indexing
            
            # First pass: identify messages with tokens and their positions
            token_message_indices = []
            processed_messages = {}
            
            for i, msg in enumerate(messages_list):
                if not msg.text:
                    continue
                
                # Process message
                processed = extraction_service.process_message(
                    message_id=f"{source.telegram_id}_{msg.id}",
                    source_id=source.telegram_id,
                    source_name=source.name,
                    text=msg.text,
                    timestamp=msg.date,
                    default_chain=chain,
                )
                
                processed_messages[i] = processed
                messages_processed += 1
                
                if processed.tokens:
                    tokens_found += len(processed.tokens)
                    token_message_indices.append(i)
            
            # Second pass: for each token mention, gather surrounding context
            for token_idx in token_message_indices:
                token_msg = processed_messages[token_idx]
                
                # Gather context messages (before and after)
                context_texts = []
                
                # Look at messages around the token mention
                # Note: Telegram messages are in reverse chronological order (newest first)
                # So "before" (earlier messages) are at higher indices
                for offset in range(-context_window, context_window + 1):
                    ctx_idx = token_idx + offset
                    if ctx_idx < 0 or ctx_idx >= len(messages_list) or ctx_idx == token_idx:
                        continue
                    
                    ctx_msg = messages_list[ctx_idx]
                    if ctx_msg.text and len(ctx_msg.text) > 10:
                        # Check if this is a meaningful message (not just a contract address)
                        text = ctx_msg.text.strip()
                        
                        # Skip if it's just a contract address or URL
                        if len(text) < 50 and (
                            text.startswith("0x") or 
                            "pump.fun" in text.lower() or
                            text.startswith("http")
                        ):
                            continue
                        
                        # Get processed version if available, or create simple version
                        if ctx_idx in processed_messages:
                            ctx_processed = processed_messages[ctx_idx]
                            context_texts.append({
                                "text": ctx_processed.original_text,
                                "sentiment": ctx_processed.sentiment,
                                "timestamp": ctx_processed.timestamp.isoformat() if ctx_processed.timestamp else None,
                            })
                        else:
                            context_texts.append({
                                "text": text[:500],
                                "sentiment": "neutral",
                                "timestamp": ctx_msg.date.isoformat() if ctx_msg.date else None,
                            })
                
                # Create the cluster message with context
                processed_dict = {
                    "id": token_msg.id,
                    "source_id": token_msg.source_id,
                    "source_name": token_msg.source_name,
                    "timestamp": token_msg.timestamp,
                    "tokens": token_msg.tokens,
                    "wallets": token_msg.wallets,
                    "sentiment": token_msg.sentiment,
                    "original_text": token_msg.original_text,
                    "context_messages": context_texts,  # NEW: surrounding discussion
                }
                
                updated = clustering_service.process_messages([processed_dict])
                for cluster in updated:
                    clusters_updated.add(cluster.id)
            
            # Update source message count
            source.total_messages += len(messages_list)
            
        except Exception as e:
            logger.error("ingest_source_error", source=source.name, error=str(e))
            continue
    
    return IngestResponse(
        messages_processed=messages_processed,
        tokens_found=tokens_found,
        clusters_updated=len(clusters_updated),
    )
