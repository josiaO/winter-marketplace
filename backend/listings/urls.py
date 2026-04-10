from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ListingViewSet, UnifiedListingView

# Accept both `/listings` and `/listings/` to avoid redirect churn.
router = DefaultRouter(trailing_slash='/?')
router.register(r'', ListingViewSet, basename='listing')

urlpatterns = [
    path('search/', UnifiedListingView.as_view(), name='unified-search'),
    path('', include(router.urls)),
]
