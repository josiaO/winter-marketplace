"""
Management command to set up default commission rules.
Run: python manage.py setup_commission_rules
"""
from django.core.management.base import BaseCommand
from commerce.models import CommissionRule
from catalog.models import Category


class Command(BaseCommand):
    help = 'Set up default commission rules for the marketplace'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing rules before creating new ones',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Deleting existing commission rules...')
            CommissionRule.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Deleted existing rules.'))

        # Default commission rule (applies to all categories)
        default_rule, created = CommissionRule.objects.get_or_create(
            name='Default Marketplace Commission',
            defaults={
                'rule_type': 'percentage',
                'percentage_value': 5.00,  # 5%
                'fixed_value': 0,
                'category': None,  # Applies to all categories
                'is_active': True,
                'priority': 0,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created default commission rule (5%)'))
        else:
            self.stdout.write('Default commission rule already exists.')

        # Example: Electronics category with higher commission
        try:
            electronics = Category.objects.filter(name__icontains='electronics').first()
            if electronics:
                electronics_rule, created = CommissionRule.objects.get_or_create(
                    name='Electronics Commission',
                    category=electronics,
                    defaults={
                        'rule_type': 'percentage',
                        'percentage_value': 7.00,  # 7% for electronics
                        'fixed_value': 0,
                        'is_active': True,
                        'priority': 10,  # Higher priority than default
                    }
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created electronics commission rule (7%) for category: {electronics.name}')
                    )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not create electronics rule: {e}'))

        # Example: High-value items with hybrid commission
        try:
            vehicles = Category.objects.filter(name__icontains='vehicle').first()
            if vehicles:
                vehicles_rule, created = CommissionRule.objects.get_or_create(
                    name='Vehicles Commission',
                    category=vehicles,
                    defaults={
                        'rule_type': 'hybrid',
                        'percentage_value': 3.00,  # 3%
                        'fixed_value': 5000.00,  # Plus 5,000 TZS flat fee
                        'is_active': True,
                        'priority': 10,
                    }
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created vehicles commission rule (3% + 5,000 TZS) for category: {vehicles.name}')
                    )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not create vehicles rule: {e}'))

        self.stdout.write(self.style.SUCCESS('\nCommission rules setup complete!'))
        self.stdout.write('\nYou can manage commission rules in the Django admin panel:')
        self.stdout.write('  - Go to /admin/commerce/commissionrule/')
        self.stdout.write('  - Create, edit, or activate/deactivate rules')
        self.stdout.write('  - Set priority (higher = takes precedence)')
        self.stdout.write('  - Leave category blank for global rules')
