"""Shipping rate resolution (server source of truth for checkout)."""
from decimal import Decimal

from django.test import TestCase, override_settings

from commerce.services.shipping_rates import (
    list_shipping_options,
    shipping_cost_for_method,
)


class ShippingRatesTests(TestCase):
    def test_default_express_fee(self):
        self.assertEqual(shipping_cost_for_method('express'), Decimal('15000.00'))

    def test_pickup_zero(self):
        self.assertEqual(shipping_cost_for_method('pickup'), Decimal('0.00'))

    def test_unknown_method(self):
        with self.assertRaises(ValueError) as ctx:
            shipping_cost_for_method('overnight_drone')
        self.assertIn('Unknown shipping_method', str(ctx.exception))

    @override_settings(
        COMMERCE_SHIPPING_RATES={
            'standard': Decimal('100.00'),
            'express': Decimal('200.00'),
            'pickup': Decimal('0'),
        }
    )
    def test_override_settings(self):
        self.assertEqual(shipping_cost_for_method('standard'), Decimal('100.00'))

    def test_list_options_contains_methods(self):
        opts = list_shipping_options()
        methods = {o['method'] for o in opts}
        self.assertTrue({'standard', 'express', 'pickup'}.issubset(methods))
        for o in opts:
            self.assertIn('fee', o)
            self.assertIn('currency', o)
