"""Telegram session management with encryption"""

import os
from typing import Optional
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.core.config import settings
from app.core.security import encrypt_data, decrypt_data


class SessionManager:
    """Manages Telegram sessions with encrypted storage"""
    
    def __init__(self):
        self.session_path = Path(settings.telegram_session_path)
        self.session_path.mkdir(parents=True, exist_ok=True)
        self._clients: dict[str, TelegramClient] = {}
    
    def get_session_file_path(self, session_name: str) -> Path:
        """Get path for session file"""
        return self.session_path / f"{session_name}.session"
    
    async def create_client(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        session_string: Optional[str] = None,
    ) -> TelegramClient:
        """Create a new Telegram client"""
        if session_string:
            # Use StringSession for portability
            session = StringSession(session_string)
        else:
            # Use file session
            session = str(self.get_session_file_path(session_name))
        
        client = TelegramClient(
            session,
            api_id,
            api_hash,
            device_model="Bloomberg Telegram",
            system_version="1.0",
            app_version="1.0.0",
        )
        
        self._clients[session_name] = client
        return client
    
    async def get_client(self, session_name: str) -> Optional[TelegramClient]:
        """Get existing client by session name"""
        return self._clients.get(session_name)
    
    async def export_session_string(self, client: TelegramClient) -> str:
        """Export session as encrypted string"""
        session_string = StringSession.save(client.session)
        return encrypt_data(session_string)
    
    async def import_session_string(self, encrypted_session: str) -> str:
        """Import encrypted session string"""
        return decrypt_data(encrypted_session)
    
    async def disconnect_client(self, session_name: str):
        """Disconnect and remove client"""
        client = self._clients.pop(session_name, None)
        if client and client.is_connected():
            await client.disconnect()
    
    async def disconnect_all(self):
        """Disconnect all clients"""
        for session_name in list(self._clients.keys()):
            await self.disconnect_client(session_name)
    
    def encrypt_credentials(self, api_id: str, api_hash: str, phone: str) -> dict:
        """Encrypt Telegram credentials for storage"""
        return {
            "api_id_encrypted": encrypt_data(str(api_id)),
            "api_hash_encrypted": encrypt_data(api_hash),
            "phone_encrypted": encrypt_data(phone),
        }
    
    def decrypt_credentials(self, encrypted: dict) -> dict:
        """Decrypt stored credentials"""
        return {
            "api_id": int(decrypt_data(encrypted["api_id_encrypted"])),
            "api_hash": decrypt_data(encrypted["api_hash_encrypted"]),
            "phone": decrypt_data(encrypted["phone_encrypted"]),
        }


session_manager = SessionManager()
