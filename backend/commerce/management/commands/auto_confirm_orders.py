from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from commerce.models import Order
from commerce.services.lifecycle import OrderLifecycleManager
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatically confirm receipt of orders that have been shipped/arrived for a configured number of days.'

    def handle(self, *args, **options):
        # Default to 7 days if not set in settings
        auto_confirm_days = getattr(settings, 'AUTO_CONFIRM_RECEIPT_DAYS', 7)
        cutoff_date = timezone.now() - timedelta(days=auto_confirm_days)
        
        # Find orders that are shipped or arrived and haven't been updated recently
        orders_to_confirm = Order.objects.filter(
            status__in=['shipped', 'arrived'],
            updated_at__lte=cutoff_date
        )
        
        count = orders_to_confirm.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS(f'No orders to auto-confirm (older than {auto_confirm_days} days).'))
            return

        confirmed_count = 0

        for order in orders_to_confirm:
            try:
                OrderLifecycleManager.confirm_delivery(order, actor=None)
                confirmed_count += 1
                logger.info(f"Auto-marked delivered order {order.id}")
            except Exception as e:
                logger.error(f"Failed to auto-confirm order {order.id}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"Error auto-confirming order {order.id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f'Successfully auto-confirmed {confirmed_count} out of {count} orders.'))
