import logging
from typing import Any, Dict

from django.conf import settings

import typesense

logger = logging.getLogger(__name__)


PRODUCTS_SCHEMA: Dict[str, Any] = {
    "name": settings.TYPESENSE_COLLECTION,
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "name", "type": "string"},
        {"name": "description", "type": "string"},
        {"name": "price", "type": "float"},
        {"name": "category", "type": "string"},
        {"name": "seller_name", "type": "string"},
        {"name": "location", "type": "string"},
    ],
    "default_sorting_field": "price",
}


def get_typesense_client() -> typesense.Client:
    return typesense.Client(
        {
            "nodes": [
                {
                    "host": settings.TYPESENSE_HOST,
                    "port": settings.TYPESENSE_PORT,
                    "protocol": settings.TYPESENSE_PROTOCOL,
                }
            ],
            "api_key": settings.TYPESENSE_API_KEY,
            "connection_timeout_seconds": 5,
        }
    )


def ensure_products_collection() -> None:
    if not settings.TYPESENSE_API_KEY:
        logger.warning(
            "TYPESENSE_API_KEY is missing; skipping collection creation."
        )
        return

    client = get_typesense_client()
    try:
        client.collections[settings.TYPESENSE_COLLECTION].retrieve()
    except Exception:
        try:
            client.collections.create(PRODUCTS_SCHEMA)
            logger.info(
                "Created Typesense collection '%s'.",
                settings.TYPESENSE_COLLECTION,
            )
        except Exception as exc:
            logger.exception("Failed to create Typesense collection: %s", exc)
            raise
