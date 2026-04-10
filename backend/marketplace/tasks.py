import json
import logging
from typing import Dict, List, Tuple
# pylint: disable=no-member

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from communications.notification_service import get_notification_service
from marketplace.models import MarketplaceItem, ProductModerationLog
from search.typesense_client import (
    ensure_products_collection,
    get_typesense_client,
)

logger = logging.getLogger(__name__)


def _build_typesense_document(product: MarketplaceItem) -> Dict[str, object]:
    return {
        "id": str(product.id),
        "name": product.title or "",
        "description": product.description or "",
        "price": float(product.price or 0),
        "category": product.category.name if product.category else "",
        "seller_name": product.owner.username if product.owner else "",
        "location": product.city or product.address or "",
    }


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=30)
def sync_product_to_typesense(self, product_id: int):  # pylint: disable=unused-argument
    """Create or update a marketplace product document in Typesense."""
    if not settings.TYPESENSE_API_KEY:
        logger.warning(
            "TYPESENSE_API_KEY missing. Skipping product sync for %s.",
            product_id,
        )
        return

    try:
        product = (
            MarketplaceItem.objects.select_related("category", "owner").get(
                id=product_id
            )
        )
    except MarketplaceItem.DoesNotExist:
        logger.warning("MarketplaceItem %s not found for Typesense sync.", product_id)
        return

    try:
        ensure_products_collection()
        client = get_typesense_client()
        document = _build_typesense_document(product)
        client.collections[settings.TYPESENSE_COLLECTION].documents.upsert(document)
        logger.info("Synced product %s to Typesense.", product_id)
    except Exception as exc:
        logger.exception("Failed syncing product %s to Typesense: %s", product_id, exc)
        raise


def _vision_credentials_dict() -> Dict[str, str]:
    if not (
        settings.GOOGLE_VISION_PROJECT_ID
        and settings.GOOGLE_VISION_PRIVATE_KEY
        and settings.GOOGLE_VISION_CLIENT_EMAIL
    ):
        return {}

    return {
        "type": "service_account",
        "project_id": settings.GOOGLE_VISION_PROJECT_ID,
        "private_key_id": settings.GOOGLE_VISION_PRIVATE_KEY_ID or "",
        "private_key": (settings.GOOGLE_VISION_PRIVATE_KEY or "").replace(
            "\\n",
            "\n",
        ),
        "client_email": settings.GOOGLE_VISION_CLIENT_EMAIL,
        "client_id": settings.GOOGLE_VISION_CLIENT_ID or "",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "auth_provider_x509_cert_url": (
            "https://www.googleapis.com/oauth2/v1/certs"
        ),
        "client_x509_cert_url": settings.GOOGLE_VISION_CLIENT_CERT_URL or "",
    }


def _is_unsafe(safe_search: Dict[str, str]) -> Tuple[bool, List[str]]:
    unsafe_labels = {"LIKELY", "VERY_LIKELY"}
    reasons: List[str] = []
    for key in ["adult", "violence", "racy", "medical", "spoof"]:
        value = str(safe_search.get(key, "UNKNOWN"))
        if value in unsafe_labels:
            reasons.append(f"{key}:{value}")
    return (len(reasons) > 0, reasons)


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def moderate_product_image(self, product_id: int):  # pylint: disable=unused-argument
    """
    Run Google Vision SafeSearch on latest product image.
    If unsafe, flag listing and notify admins.
    """
    try:
        product = (
            MarketplaceItem.objects.select_related("owner")
            .prefetch_related("media")
            .get(id=product_id)
        )
    except MarketplaceItem.DoesNotExist:
        logger.warning("MarketplaceItem %s not found for moderation.", product_id)
        return

    latest_image = (
        product.media.filter(media_type="image").order_by("-created_at").first()
    )
    if not latest_image or not latest_image.file:
        logger.info("No image found for product %s moderation.", product_id)
        return

    credentials_payload = _vision_credentials_dict()
    if not credentials_payload:
        logger.error("Google Vision credentials missing in environment variables.")
        return

    try:
        from google.cloud import vision
        from google.oauth2 import service_account
    except Exception as exc:
        logger.exception("google-cloud-vision import failed: %s", exc)
        raise

    try:
        creds = service_account.Credentials.from_service_account_info(
            credentials_payload
        )
        client = vision.ImageAnnotatorClient(credentials=creds)
        with latest_image.file.open("rb") as image_file:
            image_content = image_file.read()

        image = vision.Image(content=image_content)
        response = client.safe_search_detection(image=image)
        annotation = response.safe_search_annotation
        safe_search_result = {
            "adult": vision.Likelihood(annotation.adult).name,
            "violence": vision.Likelihood(annotation.violence).name,
            "racy": vision.Likelihood(annotation.racy).name,
            "medical": vision.Likelihood(annotation.medical).name,
            "spoof": vision.Likelihood(annotation.spoof).name,
        }
        unsafe, reasons = _is_unsafe(safe_search_result)

        ProductModerationLog.objects.create(
            product=product,
            image_url=getattr(latest_image.file, "url", ""),
            is_safe=not unsafe,
            unsafe_reasons=reasons,
            safe_search_result=safe_search_result,
        )

        if unsafe:
            product.status = "flagged"
            product.is_flagged = True
            product.flagged_reason = (
                "Unsafe image detected by Google Vision SafeSearch."
            )
            product.flagged_at = timezone.now()
            product.save(
                update_fields=[
                    "status",
                    "is_flagged",
                    "flagged_reason",
                    "flagged_at",
                    "updated_at",
                ]
            )

            notification_service = get_notification_service()
            admins = get_user_model().objects.filter(
                is_staff=True,
                is_active=True,
            )
            for admin_user in admins:
                notification_service.notify_generic(
                    user=admin_user,
                    title="Unsafe product image flagged",
                    message=(
                        f"Product #{product.id} was flagged by automated moderation."
                    ),
                    notification_type="moderation",
                    related_object_id=product.id,
                    related_object_type="marketplace_item",
                    send_push=True,
                )
            logger.warning(
                "Product %s flagged by moderation. SafeSearch=%s",
                product_id,
                json.dumps(safe_search_result),
            )
        else:
            logger.info("Product %s image passed moderation.", product_id)
    except Exception as exc:
        logger.exception("Failed moderating product %s image: %s", product_id, exc)
        raise
