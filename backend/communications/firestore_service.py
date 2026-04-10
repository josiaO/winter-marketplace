import logging
import firebase_admin
from firebase_admin import firestore
from django.conf import settings

logger = logging.getLogger(__name__)

class FirestoreService:
    """
    Manages synchronization of Django chat messages and conversations
    to Firebase Firestore for real-time frontend updates.
    """
    
    def __init__(self):
        try:
            self.db = firestore.client()
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client: {e}")
            self.db = None
            
    def is_configured(self):
        return self.db is not None
        
    def sync_conversation(self, conversation):
        """Sync basic conversation metadata"""
        if not self.is_configured():
            return
            
        try:
            doc_ref = self.db.collection('conversations').document(str(conversation.id))
            
            # Identify participants
            participants = [conversation.user.id, conversation.seller.id]
            
            data = {
                'id': conversation.id,
                'participants': participants,
                'updated_at': conversation.updated_at.isoformat() if conversation.updated_at else None,
                'is_active': conversation.is_active
            }
            
            if conversation.listing_id:
                data['listing_id'] = conversation.listing_id
                
            doc_ref.set(data, merge=True)
            
        except Exception as e:
            logger.error(f"Failed to sync conversation {conversation.id} to Firestore: {e}")

    def sync_message(self, message):
        """Sync a message to the conversation's messages subcollection"""
        if not self.is_configured():
            return
            
        try:
            # Also ensure conversation document exists/is updated
            self.sync_conversation(message.conversation)
            
            conv_ref = self.db.collection('conversations').document(str(message.conversation.id))
            msg_ref = conv_ref.collection('messages').document(str(message.id))
            
            # Using decrypted text if encrypted, or normal text
            text = message.decrypted_text if getattr(message, 'is_encrypted', False) else message.text
            if message.is_deleted:
                text = "This message was deleted"
                
            data = {
                'id': message.id,
                'sender_id': message.sender.id,
                'sender_name': message.sender.username,
                'text': text,
                'status': message.status,
                'has_attachment': bool(message.attachment),
                'is_deleted': message.is_deleted,
                'created_at': message.created_at.isoformat() if message.created_at else None,
                'read_at': message.read_at.isoformat() if hasattr(message, 'read_at') and message.read_at else None,
            }
            
            if message.reply_to_id:
                data['reply_to_id'] = message.reply_to_id
                
            msg_ref.set(data, merge=True)
            
            # Update the parent conversation's last message timestamp for sorting
            conv_ref.set({
                'last_message_at': message.created_at.isoformat() if message.created_at else None,
                'last_message_preview': text[:50] + '...' if text and len(text) > 50 else text,
                'updated_at': firestore.SERVER_TIMESTAMP
            }, merge=True)
            
        except Exception as e:
            logger.error(f"Failed to sync message {message.id} to Firestore: {e}")

    def delete_message(self, conversation_id, message_id):
        """Remove or mark message deleted in Firestore"""
        if not self.is_configured():
            return
            
        try:
            msg_ref = self.db.collection('conversations').document(str(conversation_id)).collection('messages').document(str(message_id))
            # Just do a hard delete on firestore if requested, or set is_deleted flag
            # Since our django logic uses soft delete globally, updating standard sync_message with is_deleted=True is usually enough.
            msg_ref.update({
                'is_deleted': True,
                'text': 'This message was deleted',
                'has_attachment': False
            })
        except Exception as e:
            logger.error(f"Failed to mark deleted message {message_id} in Firestore: {e}")

# Singleton instance
_firestore_service = None

def get_firestore_service():
    global _firestore_service
    if _firestore_service is None:
        _firestore_service = FirestoreService()
    return _firestore_service
