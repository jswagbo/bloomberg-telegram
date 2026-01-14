"""Wallet API routes"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.services.memory.memory_service import memory_service
from app.services.memory.queries import query_service

router = APIRouter()


@router.get("/profile/{chain}/{wallet_address}")
async def get_wallet_profile(
    chain: str,
    wallet_address: str,
    current_user: User = Depends(get_current_user),
):
    """Get wallet profile and activity history"""
    profile = await memory_service.get_wallet_profile(wallet_address, chain)
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found",
        )
    
    return profile


@router.get("/tokens/{chain}/{wallet_address}")
async def get_wallet_winning_tokens(
    chain: str,
    wallet_address: str,
    min_return: float = Query(default=2.0, ge=0),
    days: int = Query(default=30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
):
    """
    Get tokens this wallet bought before they mooned.
    Useful for tracking smart money.
    """
    result = await query_service.query(
        query_type="wallet_tokens",
        wallet=wallet_address,
        chain=chain,
        min_return=min_return,
        days=days,
    )
    return result


@router.get("/activity/{chain}")
async def get_whale_activity(
    chain: str,
    hours: int = Query(default=24, ge=1, le=168),
    min_usd: float = Query(default=10000, ge=0),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent whale activity across all tracked whales.
    """
    result = await query_service.query(
        query_type="whale_activity",
        chain=chain,
        hours=hours,
        min_usd=min_usd,
    )
    return result
