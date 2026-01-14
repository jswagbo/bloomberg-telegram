"""Telegram client service for message streaming"""

import asyncio
from typing import Optional, List, Callable, Any
from datetime import datetime
from dataclasses import dataclass, field

from telethon import TelegramClient, events
from telethon.tl.types import (
    Channel,
    Chat,
    User as TelegramUser,
    Message,
    PeerChannel,
    PeerChat,
    PeerUser,
)
from telethon.errors import FloodWaitError, ChannelPrivateError

from app.core.config import settings
from app.core.security import decrypt_data
from app.services.telegram.session import session_manager
import structlog

logger = structlog.get_logger()


@dataclass
class RawTelegramMessage:
    """Raw message from Telegram"""
    id: str
    source_id: str
    source_name: str
    source_type: str  # group, channel, bot
    timestamp: datetime
    text: str
    author: Optional[str] = None
    author_id: Optional[int] = None
    reply_to: Optional[str] = None
    media: Optional[dict] = None
    raw: Optional[dict] = None


@dataclass
class TelegramSourceConfig:
    """Configuration for a Telegram source"""
    telegram_id: str
    name: str
    source_type: str
    priority: str = "medium"
    filters: dict = field(default_factory=dict)


class TelegramService:
    """Service for connecting to Telegram and streaming messages"""
    
    def __init__(self):
        self._active_clients: dict[str, TelegramClient] = {}
        self._message_handlers: List[Callable[[RawTelegramMessage], Any]] = []
        self._running = False
    
    def add_message_handler(self, handler: Callable[[RawTelegramMessage], Any]):
        """Add a handler for incoming messages"""
        self._message_handlers.append(handler)
    
    async def connect_account(
        self,
        session_name: str,
        api_id_encrypted: str,
        api_hash_encrypted: str,
        session_string_encrypted: str,
    ) -> bool:
        """Connect a Telegram account"""
        try:
            # Decrypt credentials
            api_id = int(decrypt_data(api_id_encrypted))
            api_hash = decrypt_data(api_hash_encrypted)
            session_string = decrypt_data(session_string_encrypted)
            
            # Create client with existing session
            client = await session_manager.create_client(
                api_id=api_id,
                api_hash=api_hash,
                session_name=session_name,
                session_string=session_string,
            )
            
            # Connect
            await client.connect()
            
            if not await client.is_user_authorized():
                logger.error("telegram_not_authorized", session=session_name)
                return False
            
            self._active_clients[session_name] = client
            logger.info("telegram_connected", session=session_name)
            return True
            
        except Exception as e:
            logger.error("telegram_connect_error", session=session_name, error=str(e))
            return False
    
    async def disconnect_account(self, session_name: str):
        """Disconnect a Telegram account"""
        client = self._active_clients.pop(session_name, None)
        if client:
            await client.disconnect()
            logger.info("telegram_disconnected", session=session_name)
    
    async def start_listening(
        self,
        session_name: str,
        sources: List[TelegramSourceConfig],
    ):
        """Start listening for messages from configured sources"""
        client = self._active_clients.get(session_name)
        if not client:
            logger.error("telegram_client_not_found", session=session_name)
            return
        
        # Build list of entity IDs to listen to
        entity_ids = []
        source_map = {}  # Map entity_id to source config
        
        for source in sources:
            try:
                entity_id = int(source.telegram_id)
                entity_ids.append(entity_id)
                source_map[entity_id] = source
            except ValueError:
                # Try to resolve username
                try:
                    entity = await client.get_entity(source.telegram_id)
                    entity_ids.append(entity.id)
                    source_map[entity.id] = source
                except Exception as e:
                    logger.error("telegram_resolve_entity_error", 
                               source=source.name, error=str(e))
        
        if not entity_ids:
            logger.warning("telegram_no_valid_sources", session=session_name)
            return
        
        # Create message handler
        @client.on(events.NewMessage(chats=entity_ids))
        async def message_handler(event: events.NewMessage.Event):
            await self._handle_message(event, source_map)
        
        self._running = True
        logger.info("telegram_listening_started", 
                   session=session_name, source_count=len(entity_ids))
        
        # Keep running
        while self._running and client.is_connected():
            await asyncio.sleep(1)
    
    async def _handle_message(
        self,
        event: events.NewMessage.Event,
        source_map: dict[int, TelegramSourceConfig],
    ):
        """Handle incoming message"""
        try:
            message: Message = event.message
            chat = await event.get_chat()
            sender = await event.get_sender()
            
            # Determine source info
            chat_id = event.chat_id
            source_config = source_map.get(chat_id)
            
            if not source_config:
                return
            
            # Get source type and name
            source_type = source_config.source_type
            source_name = source_config.source_name if hasattr(source_config, 'source_name') else source_config.name
            
            # Get author info
            author = None
            author_id = None
            if sender:
                if isinstance(sender, TelegramUser):
                    author = sender.username or f"{sender.first_name or ''} {sender.last_name or ''}".strip()
                    author_id = sender.id
            
            # Get text
            text = message.text or message.message or ""
            if not text and message.media:
                text = "[Media message]"
            
            # Build media dict
            media = None
            if message.media:
                media = {
                    "type": type(message.media).__name__,
                    "has_photo": hasattr(message.media, 'photo'),
                    "has_document": hasattr(message.media, 'document'),
                }
            
            # Create raw message
            raw_msg = RawTelegramMessage(
                id=str(message.id),
                source_id=str(chat_id),
                source_name=source_name,
                source_type=source_type,
                timestamp=message.date,
                text=text,
                author=author,
                author_id=author_id,
                reply_to=str(message.reply_to_msg_id) if message.reply_to_msg_id else None,
                media=media,
                raw={
                    "message_id": message.id,
                    "chat_id": chat_id,
                    "date": message.date.isoformat(),
                    "views": getattr(message, 'views', None),
                    "forwards": getattr(message, 'forwards', None),
                }
            )
            
            # Apply filters
            if not self._passes_filters(raw_msg, source_config.filters):
                return
            
            # Call handlers
            for handler in self._message_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(raw_msg)
                    else:
                        handler(raw_msg)
                except Exception as e:
                    logger.error("message_handler_error", error=str(e))
            
        except Exception as e:
            logger.error("telegram_message_handle_error", error=str(e))
    
    def _passes_filters(self, message: RawTelegramMessage, filters: dict) -> bool:
        """Check if message passes source filters"""
        if not filters:
            return True
        
        text_lower = message.text.lower()
        
        # Check exclude keywords
        exclude_keywords = filters.get("excludeKeywords", [])
        for keyword in exclude_keywords:
            if keyword.lower() in text_lower:
                return False
        
        # Check minimum mentions (later: after entity extraction)
        # For now, pass through
        
        return True
    
    async def get_entity_info(
        self,
        session_name: str,
        entity_id: str,
    ) -> Optional[dict]:
        """Get information about a Telegram entity (group, channel, bot)"""
        client = self._active_clients.get(session_name)
        if not client:
            return None
        
        try:
            entity = await client.get_entity(int(entity_id))
            
            info = {
                "id": entity.id,
                "name": getattr(entity, 'title', None) or 
                       f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip(),
                "username": getattr(entity, 'username', None),
            }
            
            if isinstance(entity, Channel):
                info["type"] = "channel" if entity.broadcast else "group"
                info["participants_count"] = getattr(entity, 'participants_count', None)
            elif isinstance(entity, Chat):
                info["type"] = "group"
                info["participants_count"] = getattr(entity, 'participants_count', None)
            elif isinstance(entity, TelegramUser):
                info["type"] = "bot" if entity.bot else "user"
            
            return info
            
        except ChannelPrivateError:
            logger.warning("telegram_channel_private", entity_id=entity_id)
            return None
        except Exception as e:
            logger.error("telegram_get_entity_error", entity_id=entity_id, error=str(e))
            return None
    
    async def join_channel(
        self,
        session_name: str,
        channel_username: str,
    ) -> bool:
        """Join a public channel"""
        client = self._active_clients.get(session_name)
        if not client:
            return False
        
        try:
            from telethon.tl.functions.channels import JoinChannelRequest
            await client(JoinChannelRequest(channel_username))
            logger.info("telegram_channel_joined", channel=channel_username)
            return True
        except FloodWaitError as e:
            logger.warning("telegram_flood_wait", seconds=e.seconds)
            return False
        except Exception as e:
            logger.error("telegram_join_error", channel=channel_username, error=str(e))
            return False
    
    async def get_dialogs(
        self,
        session_name: str,
        limit: int = 100,
    ) -> List[dict]:
        """Get user's dialogs (chats, channels, groups)"""
        client = self._active_clients.get(session_name)
        if not client:
            return []
        
        try:
            dialogs = await client.get_dialogs(limit=limit)
            result = []
            
            for dialog in dialogs:
                entity = dialog.entity
                
                dialog_info = {
                    "id": entity.id,
                    "name": dialog.name,
                    "unread_count": dialog.unread_count,
                }
                
                if isinstance(entity, Channel):
                    dialog_info["type"] = "channel" if entity.broadcast else "group"
                    dialog_info["username"] = entity.username
                elif isinstance(entity, Chat):
                    dialog_info["type"] = "group"
                elif isinstance(entity, TelegramUser):
                    dialog_info["type"] = "bot" if entity.bot else "user"
                    dialog_info["username"] = entity.username
                else:
                    dialog_info["type"] = "unknown"
                
                result.append(dialog_info)
            
            return result
            
        except Exception as e:
            logger.error("telegram_get_dialogs_error", error=str(e))
            return []
    
    def stop_listening(self):
        """Stop listening for messages"""
        self._running = False
        logger.info("telegram_listening_stopped")


telegram_service = TelegramService()
