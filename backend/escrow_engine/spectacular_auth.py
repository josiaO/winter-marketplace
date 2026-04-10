"""drf-spectacular: document X-Api-Key for developer API (escrow_engine.api)."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class EscrowAPIKeyAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = 'escrow_engine.api.authentication.APIKeyAuthentication'
    name = 'escrowApiKey'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-Api-Key',
            'description': 'Escrow developer API key (plaintext secret; stored hashed server-side).',
        }
