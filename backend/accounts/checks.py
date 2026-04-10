from django.conf import settings
from django.core import checks
from django.db import OperationalError, connection


@checks.register()
def social_providers_config_check(app_configs, **kwargs):
    """Check that social providers configured in settings have SocialApp entries attached to the current Site.

    This check warns when a provider from `SOCIALACCOUNT_PROVIDERS` has no configured SocialApp or when the
    SocialApp is not attached to the current SITE_ID. It helps surface missing provider configuration in staging/CI.
    """
    errors = []

    # If allauth isn't installed or SOCIALACCOUNT_PROVIDERS isn't defined, nothing to check here.
    if 'allauth' not in settings.INSTALLED_APPS or not hasattr(settings, 'SOCIALACCOUNT_PROVIDERS'):
        return errors

    try:
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site
    except Exception:
        # allauth not available or models can't be imported — nothing to check
        return errors

    # Check if database tables exist (migrations may not have been run yet)
    try:
        # Try to check if the table exists
        table_names = connection.introspection.table_names()
        if 'socialaccount_socialapp' not in table_names:
            # Tables don't exist yet - skip the check
            return errors
    except Exception:
        # If we can't check tables, assume they don't exist and skip
        return errors

    site_id = getattr(settings, 'SITE_ID', None)

    for provider in settings.SOCIALACCOUNT_PROVIDERS.keys():
        try:
            # Check if any SocialApp exists for this provider
            apps = SocialApp.objects.filter(provider=provider)
            if not apps.exists():
                errors.append(
                    checks.Warning(
                        f"No SocialApp configured for provider '{provider}'",
                        hint=(
                            "Create a SocialApp in the Django admin (Social applications) for this provider "
                            "and attach it to the current Site (SITE_ID). Alternatively set provider credentials "
                            "via environment variables or configure the provider in settings.SOCIALACCOUNT_PROVIDERS."
                        ),
                        id='accounts.W001',
                    )
                )
                continue

            # If site id is set, ensure at least one SocialApp is attached to that site
            if site_id is not None:
                attached = False
                for app in apps:
                    if app.sites.filter(id=site_id).exists():
                        attached = True
                        # also check for client_id/secret presence
                        if not app.client_id or not app.secret:
                            errors.append(
                                checks.Warning(
                                    f"SocialApp for provider '{provider}' is missing client_id or secret for site {site_id}",
                                    hint=(
                                        "Fill in client_id and secret for the SocialApp in the Django admin, or set them via environment variables."
                                    ),
                                    id='accounts.W002',
                                )
                            )
                        break
                if not attached:
                    errors.append(
                        checks.Warning(
                            f"No SocialApp for provider '{provider}' is attached to Site id {site_id}",
                            hint=(
                                "Attach the SocialApp to your Site record in Django admin (Sites) or set SITE_ID to the correct site."
                            ),
                            id='accounts.W003',
                        )
                    )
        except OperationalError:
            # Database tables don't exist yet (migrations not run) - skip this check
            pass

    return errors
