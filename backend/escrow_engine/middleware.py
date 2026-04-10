"""
Extra security headers for public payment-link and escrow JSON API responses.
(Does not replace Django's SecurityMiddleware / SECURE_* settings.)
"""
from __future__ import annotations


class EscrowSecurityHeadersMiddleware:
    """Apply strict headers to escrow and payment-link paths."""

    PREFIXES = (
        '/api/v1/escrow/',
        '/api/v1/transactions/',  # developer API mounted here
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if not any(path.startswith(p) for p in self.PREFIXES):
            return response

        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'accelerometer=(), camera=(), geolocation=(), microphone=()',
        )
        return response
