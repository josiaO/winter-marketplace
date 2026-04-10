"""
Management command to check for duplicate emails and verify email-to-user mapping.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Check for duplicate emails and verify email-to-user mapping'

    def handle(self, *args, **options):
        self.stdout.write('=== User Email Report ===\n')
        
        # List all users and their emails
        users = User.objects.all().order_by('id')
        self.stdout.write(f'Total users: {users.count()}\n')
        
        for user in users:
            self.stdout.write(
                f'ID: {user.id:3d} | Username: {user.username:20s} | Email: {user.email:30s} | '
                f'Active: {user.is_active} | Superuser: {user.is_superuser}'
            )
        
        self.stdout.write('\n=== Duplicate Email Check ===\n')
        
        # Check for duplicate emails
        from django.db.models import Count
        duplicates = (
            User.objects
            .values('email')
            .annotate(count=Count('email'))
            .filter(count__gt=1, email__isnull=False)
            .exclude(email='')
        )
        
        if duplicates.exists():
            self.stdout.write(self.style.WARNING('⚠️  Found duplicate emails:'))
            for dup in duplicates:
                email = dup['email']
                users_with_email = User.objects.filter(email__iexact=email)
                self.stdout.write(f'  Email: {email} ({dup["count"]} users)')
                for u in users_with_email:
                    self.stdout.write(f'    - ID: {u.id}, Username: {u.username}')
        else:
            self.stdout.write(self.style.SUCCESS('✓ No duplicate emails found'))
        
        self.stdout.write('\n=== Email Lookup Verification ===\n')
        
        # Test email lookups
        test_emails = ['johndoe@gmail.com', 'josia.obeid@gmail.com']
        for test_email in test_emails:
            try:
                user = User.objects.get(email__iexact=test_email)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Lookup "{test_email}" -> Username: {user.username}, ID: {user.id}'
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'✗ No user found for "{test_email}"'))
            except User.MultipleObjectsReturned as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Multiple users found for "{test_email}" (data integrity issue)')
                )
