"""API routes"""

from fastapi import APIRouter

from app.api import auth, users, telegram, signals, tokens, wallets, sources, feed, trending

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(tokens.router, prefix="/tokens", tags=["tokens"])
api_router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(feed.router, prefix="/feed", tags=["feed"])
api_router.include_router(trending.router, prefix="/trending", tags=["trending"])
