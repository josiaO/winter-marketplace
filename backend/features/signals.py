# signals.py
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def sync_features_on_migrate(sender, **kwargs):
    """
    Automatically sync features after migrations run
    """
    if sender.name == 'features':
        logger.info('Auto-syncing features from registry...')
        call_command('sync_features')
