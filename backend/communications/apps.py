from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communications'
    verbose_name = 'Communications'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        import communications.signals  # noqa


