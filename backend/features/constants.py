from django.db import models
from django.utils.translation import gettext_lazy as _

class FeatureStatus(models.TextChoices):
    ACTIVE = 'active', _('Active')
    COMING_SOON = 'coming_soon', _('Coming Soon')
    DISABLED = 'disabled', _('Disabled')
