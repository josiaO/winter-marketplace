from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, CategoryFieldViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'category-fields', CategoryFieldViewSet, basename='category-field')

urlpatterns = [
    path('', include(router.urls)),
]
