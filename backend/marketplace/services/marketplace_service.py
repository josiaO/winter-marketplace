"""
Marketplace product helpers: attributes, specs normalization, price anomalies.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg

from catalog.models import Attribute
from listings.models import Listing
from marketplace.models import MarketplaceItem, ProductAttributeValue
from marketplace.validators import validate_listing_attributes
from trust.models import PriceAnomaly


def validate_attributes(category, data):
    return validate_listing_attributes(category, data)


def normalize_specs(category, data):
    if not data:
        return {}
    normalized = {}
    for key, value in data.items():
        if isinstance(key, str):
            clean_key = key.lower().replace(' ', '_').strip()
            if isinstance(value, str):
                normalized[clean_key] = value.strip()
            else:
                normalized[clean_key] = value
        else:
            normalized[key] = value
    return normalized


def save_product_attribute_values(item: MarketplaceItem, specs: dict) -> None:
    if not item.category or not specs:
        return

    category_attributes = Attribute.objects.filter(category=item.category)

    for attr in category_attributes:
        val = specs.get(attr.key) or specs.get(attr.name)
        if val is None:
            continue

        attr_value, _ = ProductAttributeValue.objects.get_or_create(
            product=item,
            attribute=attr,
        )

        attr_value.value_text = None
        attr_value.value_number = None
        attr_value.value_boolean = None
        attr_value.value_option = None

        if attr.field_type == Attribute.SELECT:
            option = attr.options.filter(value=str(val)).first()
            if option:
                attr_value.value_option = option
            else:
                attr_value.value_text = str(val)
        elif attr.field_type == Attribute.NUMBER:
            try:
                attr_value.value_number = float(val)
            except (ValueError, TypeError):
                attr_value.value_text = str(val)
        elif attr.field_type == Attribute.BOOLEAN:
            attr_value.value_boolean = bool(val)
        else:
            attr_value.value_text = str(val)

        attr_value.save()


class PriceAnomalyService:
    @staticmethod
    def detect_price_anomaly(listing):
        if not listing.category:
            return None

        similar_listings = Listing.objects.filter(
            category=listing.category,
            is_published=True,
            status='active',
        ).exclude(id=listing.id)

        if not similar_listings.exists():
            return None

        avg_price = similar_listings.aggregate(avg=Avg('price'))['avg']
        if not avg_price:
            return None

        deviation = abs(listing.price - avg_price) / avg_price

        anomaly_type = None
        score = 0.0

        if listing.price < avg_price * Decimal('0.5'):
            anomaly_type = 'too_low'
            score = min(1.0, float(deviation * 2))
        elif listing.price > avg_price * Decimal('2.0'):
            anomaly_type = 'too_high'
            score = min(1.0, float(deviation))
        elif deviation > Decimal('0.3'):
            if listing.price < avg_price:
                anomaly_type = 'price_drop'
            else:
                anomaly_type = 'price_spike'
            score = min(1.0, float(deviation))

        if anomaly_type and score > 0.3:
            listing.price_anomaly_score = float(score)
            listing.save(update_fields=['price_anomaly_score'])

            return PriceAnomaly.objects.create(
                listing=listing,
                anomaly_type=anomaly_type,
                score=score,
                expected_price_range={
                    'min': float(avg_price * Decimal('0.8')),
                    'max': float(avg_price * Decimal('1.2')),
                    'average': float(avg_price),
                },
                actual_price=listing.price,
                deviation_percentage=float(deviation * 100),
            )

        return None
