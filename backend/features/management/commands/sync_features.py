# features/management/commands/sync_features.py
from django.core.management.base import BaseCommand
from features.models import Feature
from features.features_registry import FEATURES


class Command(BaseCommand):
    help = 'Sync features from centralized registry to database'

    def handle(self, *args, **options):
        """
        Sync features from features_registry.py to database
        """
        self.stdout.write(self.style.SUCCESS('Starting feature sync from registry...'))
        
        synced_features = []
        
        for feature_config in FEATURES:
            code = feature_config.get('code')
            name = feature_config.get('name')
            description = feature_config.get('description', '')
            is_active = feature_config.get('is_active', True)
            
            # Map is_active to status field
            status = 'active' if is_active else 'coming_soon'
            
            if code and name:
                # Create or update feature
                feature, created = Feature.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'description': description,
                        'status': status,
                    }
                )
                
                action = 'Created' if created else 'Updated'
                status_emoji = '✅' if is_active else '⏳'
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{status_emoji} {action}: {name} ({code})'
                    )
                )
                synced_features.append(feature)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Feature sync complete! Synced {len(synced_features)} features.'
            )
        )
