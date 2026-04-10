from django.apps import AppConfig


class CommerceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'commerce'

    def ready(self):
        import commerce.signals  # noqa
        # Ensure Celery registers reconciliation task even if only some task modules load.
        import commerce.tasks_reconciliation  # noqa: F401
