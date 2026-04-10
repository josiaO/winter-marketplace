from django.db import models
from django.utils.translation import gettext_lazy as _

class StoreCategory(models.TextChoices):
    ELECTRONICS = 'electronics', _('Electronics')
    FASHION = 'fashion', _('Fashion')
    HOME = 'home', _('Home')
    FOOD = 'food', _('Food')
    AUTO_PARTS = 'auto_parts', _('Auto parts')
    BOOKS = 'books', _('Books')
    BEAUTY = 'beauty', _('Beauty')
    SPORTS = 'sports', _('Sports')
    OTHER = 'other', _('Other')

class VerificationStatus(models.TextChoices):
    INCOMPLETE = 'incomplete', _('Incomplete')
    PENDING_ID = 'pending_id', _('Pending ID')
    UNDER_REVIEW = 'under_review', _('Under review')
    VERIFIED = 'verified', _('Verified')
    REJECTED = 'rejected', _('Rejected')
    SUSPENDED = 'suspended', _('Suspended')
