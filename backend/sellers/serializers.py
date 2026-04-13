from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from marketplace.models import SellerProfile
from sellers.models import SellerBusinessVerification, SellerIDVerification, SellerPayoutAccount
from sellers.validators import (
    validate_business_certificate_upload,
    validate_id_front_upload,
    validate_selfie_upload,
)


from marketplace.constants import StoreCategory

def _django_to_drf(field, f):
    try:
        field(f)
        return f
    except DjangoValidationError as e:
        raise serializers.ValidationError(list(e.messages)) from e


class StoreSetupSerializer(serializers.Serializer):
    store_name = serializers.CharField(max_length=100, min_length=3)
    store_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=StoreCategory.choices),
        min_length=1,
        max_length=20,
        required=False,
    )
    # Backward compatible single-select from older clients
    store_category = serializers.ChoiceField(
        choices=StoreCategory.choices,
        required=False,
    )
    store_category_other = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    store_location = serializers.CharField(max_length=100, allow_blank=False)
    seller_type = serializers.ChoiceField(
        choices=[('product', 'Product'), ('service', 'Service')],
        required=False,
        default='product',
    )
    store_description = serializers.CharField(required=False, allow_blank=True, default='')
    store_logo = serializers.ImageField(required=False, allow_null=True)
    store_banner = serializers.ImageField(required=False, allow_null=True)

    def validate_store_categories(self, value):
        if not value:
            return value
        seen = set()
        out = []
        for v in value:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out

    def validate(self, attrs):
        cats = attrs.get('store_categories')
        legacy = attrs.get('store_category')
        if not cats and legacy:
            attrs['store_categories'] = [legacy]
        elif not cats and not legacy:
            raise serializers.ValidationError(
                {'store_categories': 'Select at least one category you sell in.'}
            )
        cats = attrs['store_categories']
        if 'other' in cats:
            other = (attrs.get('store_category_other') or '').strip()
            if not other:
                raise serializers.ValidationError(
                    {'store_category_other': 'Please describe what you sell when Other is selected.'}
                )
            attrs['store_category_other'] = other
        return attrs

    def validate_store_name(self, value):
        name = (value or '').strip()
        if len(name) < 3:
            raise serializers.ValidationError('Store name must be at least 3 characters.')
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        qs = SellerProfile.objects.filter(store_name__iexact=name)
        if user and hasattr(user, 'seller_profile'):
            qs = qs.exclude(pk=user.seller_profile.pk)
        if qs.exists():
            raise serializers.ValidationError('This store name is already taken.')
        return name


class IdentityVerificationSerializer(serializers.Serializer):
    id_type = serializers.ChoiceField(choices=[c[0] for c in SellerIDVerification.ID_TYPE_CHOICES])
    id_number = serializers.CharField(max_length=50, allow_blank=False)
    id_front_image = serializers.ImageField()
    selfie_with_id = serializers.ImageField()

    def validate_id_front_image(self, f):
        return _django_to_drf(validate_id_front_upload, f)

    def validate_selfie_with_id(self, f):
        return _django_to_drf(validate_selfie_upload, f)


class PayoutAddSerializer(serializers.Serializer):
    account_type = serializers.ChoiceField(choices=[c[0] for c in SellerPayoutAccount.ACCOUNT_TYPE_CHOICES])
    account_number = serializers.CharField(max_length=50, allow_blank=False)
    account_name = serializers.CharField(max_length=100, allow_blank=False)
    bank_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')


class PayoutVerifySerializer(serializers.Serializer):
    payout_account_id = serializers.IntegerField(min_value=1)
    verification_code = serializers.CharField(max_length=20, allow_blank=False)


class BusinessVerificationSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=200, allow_blank=False)
    business_registration_no = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=''
    )
    tin_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    bank_account_number = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    bank_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    bank_account_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    business_certificate = serializers.FileField(required=False, allow_null=True, default=None)

    def validate_business_certificate(self, f):
        if f is None:
            return f
        return _django_to_drf(validate_business_certificate_upload, f)


class AdminIdentityRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(required=True, allow_blank=False, max_length=2000)


class AdminSuspendSerializer(serializers.Serializer):
    reason = serializers.CharField(required=True, allow_blank=False, max_length=2000)


class AdminReinstateSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000, default='')


class AdminBusinessRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(required=True, allow_blank=False, max_length=2000)


class AdminIdentityApproveSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000, default='')
