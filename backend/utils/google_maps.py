import logging
from functools import lru_cache
from typing import Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

try:
    import googlemaps  # type: ignore
    from googlemaps.exceptions import (  # type: ignore
        ApiError,
        TransportError,
        Timeout,
    )
except ImportError:  # pragma: no cover - handled via requirements
    googlemaps = None  # type: ignore

    class ApiError(Exception):
        pass

    class TransportError(Exception):
        pass

    class Timeout(Exception):
        pass

logger = logging.getLogger(__name__)

MAPS_SEARCH_URL = "https://www.google.com/maps/search/"


@lru_cache(maxsize=1)
def _get_google_maps_client(api_key: str):
    """Return a memoized Google Maps client."""
    if googlemaps is None:
        raise ImproperlyConfigured(
            "googlemaps is not installed. Run `pip install googlemaps`."
        )
    return googlemaps.Client(key=api_key)


def geocode_address(address: Optional[str], city: Optional[str] = None):
    """Lookup coordinates using the official Google Maps SDK.

    Returns a dict with lat, lng and place_id when successful. None otherwise.
    """
    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", None)
    if not api_key:
        logger.debug("Skipping geocode: GOOGLE_MAPS_API_KEY not configured")
        return None

    parts = [part for part in (address, city) if part]
    if not parts:
        return None

    query = ", ".join(parts)
    timeout = getattr(settings, "GOOGLE_MAPS_GEOCODE_TIMEOUT", 5)

    try:
        client = _get_google_maps_client(api_key)
        results = client.geocode(query, timeout=timeout)
    except (ApiError, TransportError, Timeout, ValueError) as exc:
        logger.warning("Google Maps geocoding failed for '%s': %s", query, exc)
        return None

    if not results:
        logger.debug("Google Maps returned no results for '%s'", query)
        return None

    result = results[0]
    geometry = result.get("geometry", {}).get("location", {})
    return {
        "lat": geometry.get("lat"),
        "lng": geometry.get("lng"),
        "place_id": result.get("place_id"),
        "formatted_address": result.get("formatted_address"),
    }


def build_maps_url(lat: Optional[str], lng: Optional[str]) -> Optional[str]:
    """Return a browser friendly Google Maps URL for provided coordinates."""
    if lat is None or lng is None:
        return None
    return f"{MAPS_SEARCH_URL}?api=1&query={lat},{lng}"
