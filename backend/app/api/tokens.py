"""Token API routes"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, get_optional_user
from app.models.user import User
from app.services.external_apis.price_service import price_service
from app.services.memory.memory_service import memory_service
from app.services.memory.queries import query_service

router = APIRouter()


class TokenInfoResponse(BaseModel):
    address: str
    symbol: Optional[str]
    name: Optional[str]
    chain: str
    price_usd: Optional[float]
    price_change_24h: Optional[float]
    volume_24h: Optional[float]
    liquidity_usd: Optional[float]
    market_cap: Optional[float]
    dex_screener_url: Optional[str]
    source: str


class TokenHistoryResponse(BaseModel):
    token: dict
    lifecycle: dict
    mentions: List[dict]
    price_history: List[dict]


class TokenSearchResult(BaseModel):
    address: str
    symbol: Optional[str]
    name: Optional[str]
    chain: str
    price_usd: Optional[float]
    market_cap: Optional[float]


@router.get("/info/{chain}/{token_address}", response_model=TokenInfoResponse)
async def get_token_info(
    chain: str,
    token_address: str,
    user_id: Optional[str] = Depends(get_optional_user),
):
    """Get token price and info"""
    info = await price_service.get_token_info(token_address, chain)
    
    if not info:
        raise HTTPException(
            status_code=404,
            detail="Token not found",
        )
    
    return info


@router.get("/history/{chain}/{token_address}", response_model=TokenHistoryResponse)
async def get_token_history(
    chain: str,
    token_address: str,
    days: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
):
    """Get token history with mentions and price data"""
    history = await memory_service.get_token_history(token_address, chain, days)
    
    if not history:
        raise HTTPException(
            status_code=404,
            detail="Token history not found",
        )
    
    return history


@router.get("/search")
async def search_tokens(
    query: str = Query(min_length=1, max_length=100),
    chain: Optional[str] = None,
    limit: int = Query(default=10, ge=1, le=50),
    user_id: Optional[str] = Depends(get_optional_user),
):
    """Search for tokens by name or symbol"""
    results = await price_service.search_tokens(query, chain, limit)
    return {"results": results}


@router.get("/callers/{chain}/{token_address}")
async def get_token_callers(
    chain: str,
    token_address: str,
    current_user: User = Depends(get_current_user),
):
    """Get who called this token first and their track records"""
    result = await query_service.query(
        query_type="token_callers",
        token=token_address,
        chain=chain,
    )
    return result


@router.post("/batch-prices")
async def get_batch_prices(
    tokens: List[dict],  # [{"address": "...", "chain": "..."}]
    user_id: Optional[str] = Depends(get_optional_user),
):
    """Get prices for multiple tokens at once"""
    if len(tokens) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 tokens per request",
        )
    
    prices = await price_service.get_multiple_prices(tokens)
    return {"prices": prices}
