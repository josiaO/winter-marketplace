"""drf-spectacular: document FirebaseAuthentication as Bearer (reduces schema generation warnings)."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class FirebaseAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = 'accounts.authentication.FirebaseAuthentication'
    name = 'firebaseAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': 'Bearer Firebase ID token (or other backends may apply after Firebase returns None).',
        }
