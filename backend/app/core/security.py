"""Security utilities for authentication and encryption"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    """JWT token data"""
    user_id: Optional[str] = None
    exp: Optional[datetime] = None


def get_encryption_key(key: str) -> bytes:
    """Derive a Fernet-compatible key from the settings encryption key"""
    # Use PBKDF2 to derive a 32-byte key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"bloomberg_telegram_salt",  # Fixed salt for deterministic key derivation
        iterations=100000,
    )
    key_bytes = key.encode() if isinstance(key, str) else key
    return base64.urlsafe_b64encode(kdf.derive(key_bytes))


def get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption"""
    key = get_encryption_key(settings.encryption_key)
    return Fernet(key)


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    f = get_fernet()
    encrypted = f.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    f = get_fernet()
    encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
    decrypted = f.decrypt(encrypted_bytes)
    return decrypted.decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT access token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return TokenData(user_id=user_id, exp=payload.get("exp"))
    except JWTError:
        return None


def generate_session_token() -> str:
    """Generate a secure random session token"""
    return secrets.token_urlsafe(32)


def hash_message(text: str) -> str:
    """Create a hash of a message for deduplication"""
    # Normalize text before hashing
    normalized = text.lower().strip()
    # Remove extra whitespace
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode()).hexdigest()
