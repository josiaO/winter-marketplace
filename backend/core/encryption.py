"""General encryption utilities for sensitive data storage"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
import base64
import logging

logger = logging.getLogger(__name__)


class SymmetricEncryption:
    """Encrypt and decrypt text using Fernet symmetric encryption"""
    
    def __init__(self, key=None):
        """Initialize encryption with key from settings or provided key"""
        if key is None:
            key = getattr(settings, 'MESSAGE_ENCRYPTION_KEY', None)
        
        if not key:
            raise ValueError("Encryption key not configured")
        
        # Ensure key is bytes
        if isinstance(key, str):
            key = key.encode()
        
        try:
            self.cipher = Fernet(key)
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")
    
    def encrypt(self, text: str) -> str:
        """
        Encrypt plain text
        
        Args:
            text: Plain text to encrypt
            
        Returns:
            Base64 encoded encrypted text
        """
        if not text:
            return ""
        
        try:
            encrypted = self.cipher.encrypt(text.encode('utf-8'))
            return base64.b64encode(encrypted).decode('ascii')
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt encrypted text
        
        Args:
            encrypted_text: Base64 encoded encrypted text
            
        Returns:
            Decrypted plain text
        """
        if not encrypted_text:
            return ""
        
        try:
            decoded = base64.b64decode(encrypted_text.encode('ascii'))
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode('utf-8')
        except InvalidToken:
            logger.error("Decryption failed: Invalid token or corrupted data")
            return "[Decryption failed]"
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return "[Decryption failed]"


# Global encryptor instance (singleton pattern)
_encryptor = None


def get_encryptor():
    """
    Get or create the global encryptor instance
    
    Returns:
        SymmetricEncryption: Singleton encryptor instance
    """
    global _encryptor
    if _encryptor is None:
        _encryptor = SymmetricEncryption()
    return _encryptor
