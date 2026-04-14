from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdmin(BasePermission):
    """Allow access only to superusers or staff."""

    def has_permission(self, request, view):
        user = request.user
        if not user or user.is_anonymous:
            return False
        return user.is_superuser or user.is_staff

class IsAdminOrReadOnly(BasePermission):
    """Allow read access to anyone, but restrict write access to admin/staff."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if not user or user.is_anonymous:
            return False
        return user.is_superuser or user.is_staff

class IsSeller(BasePermission):
    """
    Allow access to any user with a SellerProfile.
    Suitable for onboarding and profile management.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or user.is_anonymous:
            return False
        return hasattr(user, 'seller_profile')

class IsActiveSeller(BasePermission):
    """
    Allow access only to verified sellers with an active storefront.
    Suitable for public commerce actions.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or user.is_anonymous:
            return False

        if user.is_superuser:
            return True

        # Check seller group membership
        if user.groups.filter(name='seller').exists():
            return True

        # Also accept users with an active SellerProfile
        try:
            return hasattr(user, 'seller_profile') and user.seller_profile.is_active
        except Exception:
            return False


# Legacy alias kept for backward compatibility
IsAgent = IsSeller


class HasActiveSubscription(BasePermission):
    """Placeholder - subscriptions are not implemented. Always allows access."""

    def has_permission(self, request, view):
        return True


class HasFeatureAccess(BasePermission):
    """Placeholder - feature gating is not implemented. Always allows access."""

    def has_permission(self, request, view):
        return True


class IsMicroservice(BasePermission):
    """
    Placeholder for inter-service authentication.
    Ensure 'MICROSERVICE_API_KEY' is validated when microservices communicate.
    
    Usage:
    @permission_classes([IsMicroservice])
    def my_internal_endpoint(request): ...
    """
    def has_permission(self, request, view):
        from django.conf import settings
        api_key_header = request.headers.get('X-Internal-API-Key')
        expected_key = getattr(settings, 'MICROSERVICE_API_KEY', None)
        
        if expected_key and api_key_header == expected_key:
            return True
        return False
