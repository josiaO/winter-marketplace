from django.db import models
from django.utils.translation import gettext_lazy as _

class UserVerificationStatus(models.TextChoices):
    NOT_SUBMITTED = 'not_submitted', _('Not Submitted')
    PENDING = 'pending', _('Pending Review')
    VERIFIED = 'verified', _('Verified')
    REJECTED = 'rejected', _('Rejected')

class ReportStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    UNDER_REVIEW = 'under_review', _('Under Review')
    RESOLVED = 'resolved', _('Resolved')
    DISMISSED = 'dismissed', _('Dismissed')
