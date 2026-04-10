from rest_framework.permissions import BasePermission


class IsSeller(BasePermission):
    """
    Seller-only APIs: user must have a marketplace SellerProfile.
    Does not require the store to be active (onboarding in progress is allowed).
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        try:
            return user.seller_profile is not None
        except Exception:
            return False
