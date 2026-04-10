import os
import json
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    label = 'core'

    def ready(self):
        import firebase_admin
        from firebase_admin import credentials
        
        if not firebase_admin._apps:
            firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if firebase_creds_json:
                try:
                    firebase_creds_dict = json.loads(firebase_creds_json)
                    cred = credentials.Certificate(firebase_creds_dict)
                    firebase_admin.initialize_app(cred)
                    logger.info("Firebase Admin SDK initialized successfully.")
                except Exception as e:
                    logger.warning(f"Failed to initialize Firebase Admin SDK: {e}")
            elif os.getenv('DJANGO_ENV') == 'production':
                logger.error("FIREBASE_CREDENTIALS_JSON is required in production.")
            else:
                logger.warning("FIREBASE_CREDENTIALS_JSON is not set. Firebase auth disabled.")
