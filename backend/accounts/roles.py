from django.contrib.auth.models import Group

# Role constants - only three roles exist in this marketplace
ROLE_ADMIN = 'admin'
ROLE_SELLER = 'seller'
ROLE_USER = 'user'

# Legacy alias kept for backward compat during transition
ROLE_AGENT = ROLE_SELLER


def get_user_role(user):
    """Return a simple role name for a user: 'admin', 'seller' or 'user'.

    This centralizes role logic so serializers and views don't duplicate group checks.
    """
    if not user or user.is_anonymous:
        return None
    if getattr(user, 'is_superuser', False):
        return ROLE_ADMIN
    try:
        if user.groups.filter(name='seller').exists():
            return ROLE_SELLER
        if user.groups.filter(name='agent').exists():
            return 'agent'
    except Exception:
        # defensive: if groups relation isn't available
        pass
    return ROLE_USER


def is_seller(user):
    return get_user_role(user) == ROLE_SELLER


# Legacy alias
is_agent = is_seller


def is_admin(user):
    return get_user_role(user) == ROLE_ADMIN


def is_user(user):
    return get_user_role(user) == ROLE_USER


def ensure_group(name):
    """Ensure a Group with the given name exists and return it."""
    return Group.objects.get_or_create(name=name)[0]
