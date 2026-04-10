from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('platform', views.PlatformMetricsViewSet, basename='platform-metrics')

urlpatterns = [
    # Seller
    path('seller/me/', views.SellerStatsDetailView.as_view(), name='seller-stats'),
    path('seller/me/refresh/', views.SellerStatsRefreshView.as_view(), name='seller-stats-refresh'),

    # Platform (ViewSet)
    path('', include(router.urls)),

    # Admin overrides
    path('admin/seller/<int:user_id>/', views.AdminSellerStatsView.as_view(), name='admin-seller-stats'),
]