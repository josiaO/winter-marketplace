from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SiteConfigurationViewSet

router = DefaultRouter()
router.register(r'configuration', SiteConfigurationViewSet, basename='configuration')

urlpatterns = [
    path('', include(router.urls)),
]
