from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShortLinkViewSet

router = DefaultRouter()
router.register(r'', ShortLinkViewSet, basename='shortlink')

urlpatterns = [
    path('', include(router.urls)),
]
