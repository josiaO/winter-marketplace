from django.core.management.base import BaseCommand
from accounts.roles import ensure_group


class Command(BaseCommand):
    help = 'Initialize essential user groups (e.g. agent)'

    def handle(self, *args, **options):
        groups = ['agent']
        created = []
        for g in groups:
            grp = ensure_group(g)
            created.append(g)
            self.stdout.write(self.style.SUCCESS(f'Ensured group: {g}'))

        self.stdout.write(self.style.SUCCESS('Role initialization complete.'))
