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
    opinions_found: int
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
    
    OPINION-FIRST APPROACH:
    1. Scan ALL messages for opinions/insights (not just ones with token addresses)
    2. Figure out which token each opinion is about (context, nearby mentions, etc.)
    3. Cluster opinions by token to synthesize insights
    
    This captures way more alpha because people often discuss tokens without
    explicitly mentioning contract addresses.
    """
    from app.services.telegram.client import telegram_service
    from app.services.extraction.extractor import extraction_service
    from app.services.extraction.opinion_extractor import opinion_extractor
    from app.services.extraction.token_resolver import token_resolver
    from app.services.clustering.cluster_service import clustering_service
    
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
    opinions_found = 0
    tokens_found = 0
    clusters_updated = set()
    
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
            messages_list = list(messages)
            
            # ============================================================
            # PHASE 1: Extract ALL opinions from messages
            # ============================================================
            all_messages_data = []
            for msg in messages_list:
                if not msg.text:
                    continue
                
                all_messages_data.append({
                    "text": msg.text,
                    "source_id": source.telegram_id,
                    "source_name": source.name,
                    "message_id": msg.id,
                    "timestamp": msg.date.isoformat() if msg.date else None,
                })
                messages_processed += 1
            
            # Extract opinions (regardless of token mention)
            opinions = opinion_extractor.extract_opinions_batch(all_messages_data)
            opinions_found += len(opinions)
            
            # ============================================================
            # PHASE 2: Also extract token addresses for context
            # (We still need these to resolve which token opinions are about)
            # ============================================================
            token_messages = []
            for msg in messages_list:
                if not msg.text:
                    continue
                
                processed = extraction_service.process_message(
                    message_id=f"{source.telegram_id}_{msg.id}",
                    source_id=source.telegram_id,
                    source_name=source.name,
                    text=msg.text,
                    timestamp=msg.date,
                    default_chain=chain,
                )
                
                if processed.tokens:
                    tokens_found += len(processed.tokens)
                    token_messages.append({
                        "message_id": msg.id,
                        "tokens": processed.tokens,
                        "text": msg.text,
                        "source_id": source.telegram_id,
                        "timestamp": msg.date.isoformat() if msg.date else None,
                    })
            
            # ============================================================
            # PHASE 3: Resolve which token each opinion is about
            # ============================================================
            resolved_opinions = token_resolver.resolve_tokens_batch(
                opinions=opinions,
                all_messages=all_messages_data + token_messages,
            )
            
            # ============================================================
            # PHASE 4: Cluster opinions by token
            # ============================================================
            for opinion, token_ref in resolved_opinions:
                if not token_ref:
                    # Couldn't determine which token - skip
                    continue
                
                # Create a processed message dict for clustering
                # The opinion IS the discussion content - no need to look for context
                processed_dict = {
                    "id": f"{source.telegram_id}_{opinion.message_id}",
                    "source_id": source.telegram_id,
                    "source_name": source.name,
                    "timestamp": opinion.timestamp,
                    "tokens": [{
                        "address": token_ref.address,
                        "symbol": token_ref.symbol,
                        "chain": token_ref.chain,
                    }],
                    "wallets": [],
                    "sentiment": opinion.sentiment,
                    "original_text": opinion.text,
                    # The opinion text IS the valuable content
                    "context_messages": [{
                        "text": opinion.text,
                        "sentiment": opinion.sentiment,
                        "source_name": source.name,
                        "opinion_type": opinion.opinion_type.value,
                        "key_claim": opinion.key_claim,
                        "price_target": opinion.price_target,
                        "confidence": opinion.confidence,
                    }],
                }
                
                updated = clustering_service.process_messages([processed_dict])
                for cluster in updated:
                    clusters_updated.add(cluster.id)
            
            # Also still process direct token mentions (for tracking)
            for token_msg in token_messages:
                # Find context around this token mention
                msg_id = token_msg["message_id"]
                context = []
                
                for other_msg in all_messages_data:
                    other_id = other_msg.get("message_id", 0)
                    if abs(other_id - msg_id) <= 5 and other_id != msg_id:
                        text = other_msg.get("text", "")
                        # Skip scan-like messages
                        if len(text) > 25 and "pump.fun" not in text.lower() and not text.startswith("http"):
                            context.append({
                                "text": text[:500],
                                "sentiment": "neutral",
                                "source_name": source.name,
                            })
                
                processed_dict = {
                    "id": f"{source.telegram_id}_{msg_id}",
                    "source_id": source.telegram_id,
                    "source_name": source.name,
                    "timestamp": token_msg.get("timestamp"),
                    "tokens": token_msg["tokens"],
                    "wallets": [],
                    "sentiment": "neutral",
                    "original_text": token_msg.get("text", ""),
                    "context_messages": context,
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
        opinions_found=opinions_found,
        tokens_found=tokens_found,
        clusters_updated=len(clusters_updated),
    )
