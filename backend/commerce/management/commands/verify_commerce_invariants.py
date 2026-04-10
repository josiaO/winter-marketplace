"""
Fail CI / pre-deploy checks if commerce violates Source of Truth (static model guards).

Usage:
    python manage.py verify_commerce_invariants
"""
from django.core.management.base import BaseCommand

from core.domain_guard import assert_order_model_has_no_payment_fields


class Command(BaseCommand):
    help = 'Assert commerce models respect domain boundaries (no Order payment fields, etc.).'

    def handle(self, *args, **options):
        assert_order_model_has_no_payment_fields()
        self.stdout.write(self.style.SUCCESS('Commerce invariants OK.'))
