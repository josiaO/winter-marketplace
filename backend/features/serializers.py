from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Feature, Plan, PlanFeature, SubscriptionPlan, Subscription

class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ["id", "name", "name_sw", "code", "description", "description_sw", "icon", "status", "is_global"]

class PlanFeatureSerializer(serializers.ModelSerializer):
    feature = FeatureSerializer()
    class Meta:
        model = PlanFeature
        fields = ("feature", "included")

class PlanSerializer(serializers.ModelSerializer):
    features = serializers.SerializerMethodField()
    
    class Meta:
        model = Plan
        fields = '__all__'
    
    @extend_schema_field(FeatureSerializer(many=True))
    def get_features(self, obj):
        """Flatten features from PlanFeature to just Feature objects"""
        plan_features = obj.features.select_related('feature').filter(included=True)
        return FeatureSerializer([pf.feature for pf in plan_features], many=True).data

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Legacy subscription plan serializer for payment system"""
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'price', 'duration_days', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for user subscriptions"""
    plan = PlanSerializer(read_only=True)
    
    class Meta:
        model = Subscription
        fields = ['id', 'user', 'plan', 'start_date', 'end_date', 'is_active', 'is_trial', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
