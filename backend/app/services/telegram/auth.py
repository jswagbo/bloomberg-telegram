"""Telegram authentication service"""

import asyncio
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PasswordHashInvalidError,
    FloodWaitError,
)
from telethon.sessions import StringSession

from app.core.config import settings
from app.core.security import encrypt_data, decrypt_data
from app.services.telegram.session import session_manager
import structlog

logger = structlog.get_logger()


class AuthState(str, Enum):
    """Authentication state machine"""
    INITIAL = "initial"
    AWAITING_CODE = "awaiting_code"
    AWAITING_2FA = "awaiting_2fa"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


@dataclass
class AuthSession:
    """Temporary auth session during authentication flow"""
    client: TelegramClient
    api_id: int
    api_hash: str
    phone: str
    state: AuthState
    phone_code_hash: Optional[str] = None
    error: Optional[str] = None


class TelegramAuthService:
    """Service for handling Telegram authentication flow"""
    
    def __init__(self):
        self._pending_auths: dict[str, AuthSession] = {}
    
    async def start_auth(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_name: str,
    ) -> Tuple[AuthState, Optional[str]]:
        """
        Start authentication flow.
        Returns (state, error_message)
        """
        try:
            # Create new client
            client = await session_manager.create_client(
                api_id=api_id,
                api_hash=api_hash,
                session_name=session_name,
            )
            
            # Connect to Telegram
            await client.connect()
            
            # Check if already authorized
            if await client.is_user_authorized():
                auth_session = AuthSession(
                    client=client,
                    api_id=api_id,
                    api_hash=api_hash,
                    phone=phone,
                    state=AuthState.AUTHENTICATED,
                )
                self._pending_auths[session_name] = auth_session
                return AuthState.AUTHENTICATED, None
            
            # Send code request
            result = await client.send_code_request(phone)
            
            auth_session = AuthSession(
                client=client,
                api_id=api_id,
                api_hash=api_hash,
                phone=phone,
                state=AuthState.AWAITING_CODE,
                phone_code_hash=result.phone_code_hash,
            )
            self._pending_auths[session_name] = auth_session
            
            logger.info("auth_code_sent", phone=phone[:4] + "****", session=session_name)
            return AuthState.AWAITING_CODE, None
            
        except FloodWaitError as e:
            error = f"Too many attempts. Please wait {e.seconds} seconds."
            logger.error("auth_flood_wait", seconds=e.seconds)
            return AuthState.ERROR, error
            
        except Exception as e:
            error = str(e)
            logger.error("auth_start_error", error=error)
            return AuthState.ERROR, error
    
    async def verify_code(
        self,
        session_name: str,
        code: str,
    ) -> Tuple[AuthState, Optional[str]]:
        """
        Verify the phone code.
        Returns (state, error_message)
        """
        auth_session = self._pending_auths.get(session_name)
        if not auth_session:
            return AuthState.ERROR, "No pending authentication found"
        
        if auth_session.state != AuthState.AWAITING_CODE:
            return AuthState.ERROR, f"Invalid state: {auth_session.state}"
        
        try:
            await auth_session.client.sign_in(
                phone=auth_session.phone,
                code=code,
                phone_code_hash=auth_session.phone_code_hash,
            )
            
            auth_session.state = AuthState.AUTHENTICATED
            logger.info("auth_code_verified", session=session_name)
            return AuthState.AUTHENTICATED, None
            
        except SessionPasswordNeededError:
            auth_session.state = AuthState.AWAITING_2FA
            logger.info("auth_2fa_required", session=session_name)
            return AuthState.AWAITING_2FA, None
            
        except PhoneCodeInvalidError:
            return AuthState.AWAITING_CODE, "Invalid code. Please try again."
            
        except PhoneCodeExpiredError:
            # Need to restart auth flow
            auth_session.state = AuthState.ERROR
            return AuthState.ERROR, "Code expired. Please restart authentication."
            
        except Exception as e:
            error = str(e)
            logger.error("auth_code_verify_error", error=error)
            return AuthState.ERROR, error
    
    async def verify_2fa(
        self,
        session_name: str,
        password: str,
    ) -> Tuple[AuthState, Optional[str]]:
        """
        Verify 2FA password.
        Returns (state, error_message)
        """
        auth_session = self._pending_auths.get(session_name)
        if not auth_session:
            return AuthState.ERROR, "No pending authentication found"
        
        if auth_session.state != AuthState.AWAITING_2FA:
            return AuthState.ERROR, f"Invalid state: {auth_session.state}"
        
        try:
            await auth_session.client.sign_in(password=password)
            
            auth_session.state = AuthState.AUTHENTICATED
            logger.info("auth_2fa_verified", session=session_name)
            return AuthState.AUTHENTICATED, None
            
        except PasswordHashInvalidError:
            return AuthState.AWAITING_2FA, "Invalid password. Please try again."
            
        except Exception as e:
            error = str(e)
            logger.error("auth_2fa_verify_error", error=error)
            return AuthState.ERROR, error
    
    async def complete_auth(
        self,
        session_name: str,
    ) -> Tuple[Optional[str], Optional[dict]]:
        """
        Complete authentication and return encrypted session.
        Returns (encrypted_session_string, user_info)
        """
        auth_session = self._pending_auths.get(session_name)
        if not auth_session:
            return None, None
        
        if auth_session.state != AuthState.AUTHENTICATED:
            return None, None
        
        try:
            # Get user info
            me = await auth_session.client.get_me()
            user_info = {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
            }
            
            # Export and encrypt session
            session_string = StringSession.save(auth_session.client.session)
            encrypted_session = encrypt_data(session_string)
            
            logger.info("auth_completed", session=session_name, user_id=me.id)
            return encrypted_session, user_info
            
        except Exception as e:
            logger.error("auth_complete_error", error=str(e))
            return None, None
    
    async def cancel_auth(self, session_name: str):
        """Cancel pending authentication"""
        auth_session = self._pending_auths.pop(session_name, None)
        if auth_session and auth_session.client.is_connected():
            await auth_session.client.disconnect()
        logger.info("auth_cancelled", session=session_name)
    
    def get_auth_state(self, session_name: str) -> Optional[AuthState]:
        """Get current auth state for session"""
        auth_session = self._pending_auths.get(session_name)
        return auth_session.state if auth_session else None


telegram_auth_service = TelegramAuthService()
