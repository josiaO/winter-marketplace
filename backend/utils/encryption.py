"""
End-to-end encryption utilities for secure messaging
"""
from cryptography.fernet import Fernet
from django.conf import settings
import os
import base64
import logging

logger = logging.getLogger(__name__)


class MessageEncryption:
    """Handle message encryption and decryption"""
    
    def __init__(self):
        # Get or create encryption key from settings
        self.key = getattr(settings, 'MESSAGE_ENCRYPTION_KEY', None)
        if not self.key:
            # Generate a key from a settings string
            key_string = getattr(settings, 'SECRET_KEY', 'default-secret')
            # Derive a 32-byte key from the secret key
            self.key = base64.urlsafe_b64encode(
                key_string.encode().ljust(32)[:32]
            )
        self.cipher = Fernet(self.key)
    
    def encrypt_message(self, message: str) -> str:
        """Encrypt a message"""
        try:
            encrypted = self.cipher.encrypt(message.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}", exc_info=True)
            return message
    
    def decrypt_message(self, encrypted_message: str) -> str:
        """Decrypt a message"""
        try:
            decrypted = self.cipher.decrypt(encrypted_message.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}", exc_info=True)
            return encrypted_message


# Singleton instance
_encryption = None


def get_encryption():
    """Get the encryption instance"""
    global _encryption
    if _encryption is None:
        _encryption = MessageEncryption()
    return _encryption
