import base64
import os
import sys
import django
import asyncio
import websockets

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

def get_token():
    user = User.objects.first()
    if not user:
        return None, None
    token = AccessToken.for_user(user)
    return str(token), user.username

def _b64url_encode_jwt(jwt: str) -> str:
    return base64.urlsafe_b64encode(jwt.encode()).decode().rstrip("=")


async def test_websocket(token, username):
    print(f"Generated token for user {username}: {token[:24]}...")

    # Prefer Sec-WebSocket-Protocol (matches frontend + JWTAuthMiddleware); ?token= still supported.
    ws_url = "ws://127.0.0.1:8000/ws/notifications/"
    subprotocols = ["sd-jwt", _b64url_encode_jwt(token)]
    print(f"Connecting to: {ws_url} with subprotocols={subprotocols[0]}, <jwt b64url>")

    try:
        # Standard connect call
        async with websockets.connect(
            ws_url, 
            subprotocols=subprotocols
        ) as websocket:
            print("Successfully connected!")
            
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"Received: {msg}")
            except asyncio.TimeoutError:
                print("No initial message received within 2 seconds.")
                
    except Exception as e:
        print(f"WebSocket connection failed: {e}")

if __name__ == "__main__":
    token, username = get_token()
    if token:
        asyncio.run(test_websocket(token, username))
    else:
        print("No users found")
