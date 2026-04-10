from django.apps import AppConfig


class EscrowEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'escrow_engine'
    verbose_name = 'Escrow Engine'

    def ready(self):
        import escrow_engine.signals  # noqa: F401

        try:
            import escrow_engine.spectacular_auth  # noqa: F401 — OpenApiAuthenticationExtension
        except Exception:
            pass
