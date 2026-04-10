import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """
    A simple task to verify that Celery is working correctly.
    You can trigger this from the Django shell using:
    from backend.celery import debug_task
    debug_task.delay()
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Celery is working!")
    print(f'Request: {self.request!r}')
