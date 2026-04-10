from django.db import models
from features.constants import FeatureStatus

class Feature(models.Model):
    name = models.CharField(max_length=100)
    name_sw = models.CharField(max_length=100, blank=True, null=True, help_text="Swahili name")
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    description_sw = models.TextField(blank=True, null=True, help_text="Swahili description")
    icon = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=FeatureStatus.choices, default=FeatureStatus.ACTIVE)
    is_global = models.BooleanField(default=False, help_text="If true, available to all users regardless of plan")

    def __str__(self):
        return self.name


class Plan(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    name_sw = models.CharField(max_length=100, blank=True, null=True, help_text="Swahili name")
    description = models.TextField(blank=True)
    description_sw = models.TextField(blank=True, null=True, help_text="Swahili description")
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    highlight = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class PlanFeature(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="features")
    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name="plans")

    included = models.BooleanField(default=True)

    class Meta:
        unique_together = ("plan", "feature")

    def __str__(self):
        return f"{self.plan.title} → {self.feature.name}"


# For backward compatibility with properties app Payment model
class SubscriptionPlan(models.Model):
    """Legacy subscription plan model for payment tracking"""
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.price})"


class Subscription(models.Model):
    """User subscription to a plan"""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='subscriptions')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_trial = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.plan.title}"
