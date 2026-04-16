from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'User Accounts and Profiles'

    def ready(self):
        # Import signal handlers to ensure they are registered when the app is ready
        import accounts.signals  # noqa: F401
        
        # Import checks to register system checks at app ready
        import accounts.checks  # noqa: F401
        
        # OpenApiAuthenticationExtension for Firebase
        import accounts.spectacular_auth  # noqa: F401
