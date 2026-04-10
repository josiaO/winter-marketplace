from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'catalog'
    
    def ready(self):
        """Import admin when app is ready to ensure registration."""
        try:
            import catalog.admin  # noqa: F401
        except ImportError:
            pass