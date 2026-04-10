from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'User Accounts and Profiles'

    def ready(self):
        # Import signal handlers to ensure they are registered when the app is ready
        try:
            import accounts.signals  # noqa: F401
        except Exception:
            # Avoid failing app startup if signals module has issues
            pass
        # Import checks to register system checks at app ready
        try:
            import accounts.checks  # noqa: F401
        except Exception:
            # Non-fatal: don't block startup if checks have issues
            pass
        try:
            import accounts.spectacular_auth  # noqa: F401 — OpenApiAuthenticationExtension for Firebase
        except Exception:
            pass
