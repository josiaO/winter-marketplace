from django.db import models
from django.utils.translation import gettext_lazy as _

class ListingStatus(models.TextChoices):
    DRAFT = 'draft', _('Draft')
    PENDING = 'pending', _('Pending review')
    ACTIVE = 'active', _('Active')
    REJECTED = 'rejected', _('Rejected')
    FLAGGED = 'flagged', _('Flagged')
    SOLD = 'sold', _('Sold')
    RENTED = 'rented', _('Rented')
    SUSPENDED = 'suspended', _('Suspended')
    ARCHIVED = 'archived', _('Archived')
