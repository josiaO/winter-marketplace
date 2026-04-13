from .views import CartViewSet, OrderViewSet, WishlistViewSet
from .offer_views import ListingOfferViewSet
from rest_framework.routers import DefaultRouter
from django.urls import path, include

router = DefaultRouter()
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'wishlist', WishlistViewSet, basename='wishlist')
router.register(r'offers', ListingOfferViewSet, basename='listing-offer')

urlpatterns = [
    path('', include(router.urls)),
]
