import base64
from typing import Optional

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from urllib.parse import parse_qs

from django.core.cache import cache

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


@database_sync_to_async
def _get_user_from_ticket(ticket: str) -> Optional[User]:
    """
    Validate a one-time ticket against cache.
    If valid, returns the User and clears the ticket.
    """
    cache_key = f"ws_ticket_{ticket}"
    user_id = cache.get(cache_key)
    if not user_id:
        return None
    
    # Immediately clear the ticket (one-time use)
    cache.delete(cache_key)
    
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


def _extract_jwt_token(scope) -> Optional[str]:
    """
    Extracts a JWT token from subprotocols, cookies, or query string.
    Note: Returns 'TICKET:<val>' if a ticket is found instead of a JWT.
    """
    # 0) Handshake Ticket (Primary for browser clients in secure HttpOnly environment)
    query_string = scope.get("query_string", b"").decode()
    query_params = parse_qs(query_string)
    ticket = query_params.get("ticket", [None])[0]
    if ticket:
        return f"TICKET:{ticket}"

    # 1) Subprotocol (Fallback / Direct API clients)
    t = _token_from_subprotocols(scope)
    if t:
        return t

    # 2) Query string (Legacy fallback)
    t = query_params.get("token", [None])[0]
    if t:
        return t

    # 3) Cookie (Same-site deployments)
    return _token_from_cookie_header(_get_header(scope, b"cookie"))


@database_sync_to_async
def get_user(token_key):
    try:
        access_token = AccessToken(token_key)
        user_id = access_token["user_id"]
        user = User.objects.get(id=user_id)
        print(f"✅ WebSocket Auth Success: User {user.username} (ID: {user.id})")
        return user
    except (InvalidToken, TokenError) as e:
        print(f"❌ WebSocket Auth Failed (Token Error): {e}")
        return AnonymousUser()
    except User.DoesNotExist:
        print(f"❌ WebSocket Auth Failed (User Not Found)")
        return AnonymousUser()
    except Exception as e:
        import traceback
        print(f"❌ WebSocket Auth Unexpected Error: {e}")
        traceback.print_exc()
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
        try:
            print(f"DEBUG: WebSocket request for {scope.get('path')} from {scope.get('client')}")
            identifier = _extract_jwt_token(scope)
            
            if identifier:
                if identifier.startswith("TICKET:"):
                    ticket = identifier.split(":", 1)[1]
                    user = await _get_user_from_ticket(ticket)
                    if user:
                        print(f"✅ WebSocket Auth Success: User {user.username} via Ticket")
                        scope["user"] = user
                    else:
                        print(f"❌ WebSocket Auth Failed: Invalid or expired Ticket")
                        scope["user"] = AnonymousUser()
                else:
                    scope["user"] = await get_user(identifier)
            else:
                print("DEBUG: No auth identifier found in WebSocket request")
                scope["user"] = AnonymousUser()

            return await self.app(scope, receive, send)
        except Exception as e:
            import traceback
            print(f"❌ WebSocket Middleware Error: {e}")
            traceback.print_exc()
            raise
