import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, inline_serializer

from django.conf import settings

from .typesense_client import (
    ensure_products_collection,
    get_typesense_client,
)

logger = logging.getLogger(__name__)


class MarketplaceSearchView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, description="Search query"),
        ],
        responses={
            200: inline_serializer("SearchResponse", fields={
                "results": inline_serializer("SearchResult", fields={
                    "id": serializers.CharField(),
                    "name": serializers.CharField(),
                    "description": serializers.CharField(),
                    "price": serializers.FloatField(),
                    "category": serializers.CharField(),
                    "seller_name": serializers.CharField(),
                    "location": serializers.CharField(),
                    "score": serializers.FloatField()
                }, many=True),
                "count": serializers.IntegerField()
            })
        }
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"results": [], "count": 0})

        if not settings.TYPESENSE_API_KEY:
            logger.error("TYPESENSE_API_KEY missing. Cannot perform search.")
            return Response(
                {"error": "Search service is not configured.", "results": []},
                status=503,
            )

        try:
            ensure_products_collection()
            client = get_typesense_client()
            search_parameters = {
                "q": query,
                "query_by": "name,description,category,seller_name,location",
                "sort_by": "_text_match:desc",
                "per_page": 20,
            }
            response = (
                client.collections[settings.TYPESENSE_COLLECTION]
                .documents.search(search_parameters)
            )
            hits = response.get("hits", [])
            results = [
                {
                    "id": hit.get("document", {}).get("id"),
                    "name": hit.get("document", {}).get("name"),
                    "description": hit.get("document", {}).get("description"),
                    "price": hit.get("document", {}).get("price"),
                    "category": hit.get("document", {}).get("category"),
                    "seller_name": hit.get("document", {}).get("seller_name"),
                    "location": hit.get("document", {}).get("location"),
                    "score": hit.get("text_match"),
                }
                for hit in hits
            ]
            return Response({"results": results, "count": len(results)})
        except Exception as exc:
            logger.exception("Typesense search failed: %s", exc)
            return Response(
                {"error": "Search failed. Please try again later."},
                status=500,
            )
