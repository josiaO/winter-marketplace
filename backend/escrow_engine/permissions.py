"""
escrow_engine.permissions
--------------------------
Permission classes for the escrow engine API.
"""
from rest_framework.permissions import BasePermission, IsAuthenticated


class IsAdminUser(BasePermission):
    """Only Django staff / superusers."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (request.user.is_staff or request.user.is_superuser))


class IsTransactionParty(BasePermission):
    """
    Allow access only to the buyer or seller of a transaction.
    Admin can always access.
    """
    def has_object_permission(self, request, view, obj):
        from escrow_engine.models import Transaction
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        if isinstance(obj, Transaction):
            return obj.buyer_user == user or obj.seller_user == user
        # For Dispute / Payout objects access the parent transaction
        txn = getattr(obj, 'transaction', None)
        if txn:
            return txn.buyer_user == user or txn.seller_user == user
        return False


class IsTransactionBuyer(BasePermission):
    """Only the buyer of the transaction (or admin)."""
    def has_object_permission(self, request, view, obj):
        from escrow_engine.models import Transaction
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        txn = obj if isinstance(obj, Transaction) else getattr(obj, 'transaction', None)
        return txn and txn.buyer_user == user
