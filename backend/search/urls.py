from django.urls import path

from .views import MarketplaceSearchView

urlpatterns = [
    path("", MarketplaceSearchView.as_view(), name="typesense-search"),
]
