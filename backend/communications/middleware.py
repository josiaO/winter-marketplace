import base64
from typing import Optional

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from urllib.parse import parse_qs

User = get_user_model()

AUTH_COOKIE_NAMES = ("smartdalali_auth_token", "auth_token")
# Client sends JWT via Sec-WebSocket-Protocol: sd-jwt, <base64url(token)> (avoids token in URL / query logs)
WS_SUBPROTOCOL_SCHEME = "sd-jwt"


def _get_header(scope, name: bytes) -> Optional[bytes]:
    for key, value in scope.get("headers") or []:
        if key.lower() == name.lower():
            return value
    return None


def _token_from_cookie_header(cookie_header: Optional[bytes]) -> Optional[str]:
    if not cookie_header:
        return None
    try:
        text = cookie_header.decode("utf-8")
    except UnicodeDecodeError:
        return None
    for part in text.split(";"):
        part = part.strip()
        for name in AUTH_COOKIE_NAMES:
            prefix = f"{name}="
            if part.startswith(prefix):
                return part[len(prefix) :].strip() or None
    return None


def _b64url_decode(segment: str) -> Optional[str]:
    if not segment:
        return None
    padded = segment + "=" * ((4 - len(segment) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _token_from_subprotocols(scope) -> Optional[str]:
    subs = scope.get("subprotocols") or []
    if (
        isinstance(subs, (list, tuple))
        and len(subs) >= 2
        and subs[0] == WS_SUBPROTOCOL_SCHEME
    ):
        return _b64url_decode(subs[1])
    raw = _get_header(scope, b"sec-websocket-protocol")
    if not raw:
        return None
    try:
        parts = [p.strip() for p in raw.decode("utf-8").split(",")]
    except UnicodeDecodeError:
        return None
    if len(parts) >= 2 and parts[0] == WS_SUBPROTOCOL_SCHEME:
        return _b64url_decode(parts[1])
    return None


def _extract_jwt_token(scope) -> Optional[str]:
    # 1) Subprotocol (preferred — not in URL / query string)
    t = _token_from_subprotocols(scope)
    if t:
        return t
    # 2) Query string (legacy)
    query_string = scope.get("query_string", b"").decode()
    query_params = parse_qs(query_string)
    t = query_params.get("token", [None])[0]
    if t:
        return t
    # 3) Cookie on WebSocket handshake (same-site API + app)
    return _token_from_cookie_header(_get_header(scope, b"cookie"))


@database_sync_to_async
def get_user(token_key):
    try:
        access_token = AccessToken(token_key)
        user_id = access_token["user_id"]
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist) as e:
        print(f"❌ WebSocket Auth Failed: {e}")  # Debug log
        return AnonymousUser()
    except Exception as e:
        print(f"❌ WebSocket Auth Unexpected Error: {e}")  # specific log
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Authenticate WebSocket connections via (in order):
    1. Sec-WebSocket-Protocol: sd-jwt, <base64url(JWT)> — avoids tokens in URLs
    2. Query string ?token= (legacy)
    3. Cookie smartdalali_auth_token / auth_token (same-site deployments)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = _extract_jwt_token(scope)
        if token:
            scope["user"] = await get_user(token)
        else:
            scope["user"] = AnonymousUser()

        return await self.app(scope, receive, send)
