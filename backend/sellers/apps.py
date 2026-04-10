from django.apps import AppConfig


class SellersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sellers'
    verbose_name = 'Seller onboarding'

    def ready(self):
        from . import signals  # noqa: F401
