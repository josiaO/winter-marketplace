from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MarketplaceItemViewSet, SellerProfileViewSet, StoreViewSet,
    SellerPaymentMethodViewSet,
    favorites_list_add, favorites_remove
)

router = DefaultRouter()
router.register(r'items', MarketplaceItemViewSet)
router.register(r'sellers', SellerProfileViewSet, basename='seller')
router.register(r'stores', StoreViewSet, basename='store')
router.register(r'payment-methods', SellerPaymentMethodViewSet, basename='payment-method')


urlpatterns = [
    path('favorites/', favorites_list_add, name='favorites-list-add'),
    path('favorites/<int:favorite_id>/', favorites_remove, name='favorites-remove'),
    path('', include(router.urls)),
]
