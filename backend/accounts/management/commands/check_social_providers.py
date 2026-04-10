from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Check social providers configuration and report missing SocialApp entries or misconfigurations.'

    def handle(self, *args, **options):
        try:
            from allauth.socialaccount.models import SocialApp
            from django.contrib.sites.models import Site
        except Exception as e:
            self.stdout.write(self.style.WARNING('django-allauth or sites framework not available. Skipping check.'))
            return

        site_id = getattr(settings, 'SITE_ID', None)

        providers = {}
        if hasattr(settings, 'SOCIALACCOUNT_PROVIDERS'):
            providers = settings.SOCIALACCOUNT_PROVIDERS.keys()
        else:
            # fall back to well-known providers if settings not provided
            providers = ['google', 'facebook', 'microsoft', 'apple']

        any_issues = False

        for provider in providers:
            apps = SocialApp.objects.filter(provider=provider)
            if not apps.exists():
                any_issues = True
                self.stdout.write(self.style.WARNING(f"[MISSING] No SocialApp configured for provider '{provider}'"))
                continue

            # check attachment and credentials
            attached = False
            for app in apps:
                if site_id is None or app.sites.filter(id=site_id).exists():
                    attached = True
                    if not app.client_id or not app.secret:
                        any_issues = True
                        self.stdout.write(self.style.WARNING(
                            f"[BAD] SocialApp for provider '{provider}' (id={app.id}) is missing client_id or secret"
                        ))
            if not attached:
                any_issues = True
                self.stdout.write(self.style.WARNING(
                    f"[UNATTACHED] SocialApp(s) for provider '{provider}' exist but none attached to Site id {site_id}"
                ))

        if not any_issues:
            self.stdout.write(self.style.SUCCESS('All checked social providers appear to be configured and attached.'))
        else:
            self.stdout.write(self.style.WARNING('Some social provider configurations are missing or incomplete.'))
