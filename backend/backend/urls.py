from django.contrib import admin
from django.urls import path, include

from django.http import HttpResponse, JsonResponse
from django.views.generic.base import RedirectView

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from backend.schema_views import StaffSpectacularAPIView, StaffSpectacularRedocView

# Trigger admin dashboard customizations
from . import admin as admin_dashboard  # noqa: F401
from insights.views import seller_stats_summary

from django.conf import settings
from django.conf.urls.static import static

import os

def empty_favicon(request):
    return HttpResponse("", content_type="image/x-icon")

def chrome_devtools_handler(request):
    """Handle Chrome DevTools well-known endpoint to suppress 404 warnings."""
    return HttpResponse(status=204)  # No Content

def api_root(request):
    """API root endpoint showing available API endpoints."""
    return JsonResponse({
        "message": "DigitalDalali API",
        "version": "v1",
        "endpoints": {
            "accounts": "/api/v1/accounts/",
            "communications": "/api/v1/communications/",
            "features": "/api/v1/features/",
            "insights": "/api/v1/insights/",
            "support": "/api/v1/support/",
            "shortlinks": "/api/v1/shortlinks/",
            "seller_stats": "/api/v1/insights/seller-stats/",
            "marketplace": "/api/v1/marketplace/",
            "listings": "/api/v1/listings/",
            "catalog": "/api/v1/catalog/",
            "commerce": "/api/v1/commerce/",
            "trust": "/api/v1/trust/",
            "core": "/api/v1/core/",
            "analytics": "/api/v1/analytics/",
            "escrow": "/api/v1/escrow/",
        },
        "documentation": {
            "schema": "/api/schema/",
            "redoc": "/api/docs/redoc/",
        },
        "admin": "/admin/",
        "health": "/health/",
    })

from shortlinks.views import redirect_view

from sellers.urls import admin_urlpatterns as sellers_admin_urlpatterns

from backend.health import health_check, readiness_check

# Custom Error Handlers
handler404 = 'backend.error_handlers.handler404'
handler500 = 'backend.error_handlers.handler500'
handler403 = 'backend.error_handlers.handler403'
handler400 = 'backend.error_handlers.handler400'

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('health/ready/', readiness_check, name='readiness_check'),
    # API root endpoint
    path("api/v1/", api_root, name="api-root"),
    # Common mistaken URLs → v1 root (avoids 404 on /api or /api/)
    path("api/", RedirectView.as_view(url="/api/v1/", permanent=False)),
    path("api", RedirectView.as_view(url="/api/v1/", permanent=False)),

    # Redirect root to the API base so visiting the site shows your API.
    path("", RedirectView.as_view(url="/api/v1/", permanent=False)),

    path('admin/', admin.site.urls),
    path('s/<str:code>/', redirect_view, name='shortlink-redirect'),
    path('accounts/', include('allauth.urls')),
    # path('api/v1/properties/', include('properties.urls')), # Decommissioned
    # Unified API root
    path('api/v1/communications/', include('communications.urls')),
    path('api/v1/insights/', include('insights.urls')),
    path("api/v1/features/", include("features.urls")),
    path('api/v1/accounts/', include('accounts.urls')),
    path('api/v1/shortlinks/', include('shortlinks.urls')),
    path('api/v1/marketplace/', include('marketplace.urls')),
    # Sellers onboarding/admin endpoints
    #
    # Canonical (versioned) routes for frontend proxy compatibility:
    # - Next.js proxies same-origin `/api/v1/*` to Django.
    path('api/v1/sellers/', include(('sellers.urls', 'sellers'), namespace='sellers')),
    path('api/v1/admin/sellers/', include((sellers_admin_urlpatterns, 'sellers_admin'), namespace='sellers_admin')),
    #
    # Backward-compatible legacy mounts:
    path('api/sellers/', include(('sellers.urls', 'sellers'), namespace='sellers_legacy')),
    path('api/admin/sellers/', include((sellers_admin_urlpatterns, 'sellers_admin'), namespace='sellers_admin_legacy')),
    # Support both trailing-slash and no-slash base prefixes to prevent 301s.
    path('api/v1/listings', include('listings.urls')),
    path('api/v1/listings/', include('listings.urls')),
    # catalog — router handles both slash variants internally
    path('api/v1/catalog/', include('catalog.urls')),
    path('api/v1/commerce/', include('commerce.urls')),
    path('api/v1/trust/', include('trust.urls')),
    path('api/v1/core/', include('core.urls')),
    path('api/v1/analytics/', include('analytics.urls')),
    path('api/v1/escrow/', include('escrow_engine.urls')),
    path('api/v1/search/', include('search.urls')),
    path(
        'api/schema/',
        SpectacularAPIView.as_view() if settings.DEBUG else StaffSpectacularAPIView.as_view(),
        name='api-schema',
    ),
    path(
        'api/docs/redoc/',
        (
            SpectacularRedocView.as_view(url_name='api-schema')
            if settings.DEBUG
            else StaffSpectacularRedocView.as_view(url_name='api-schema')
        ),
        name='api-docs-redoc',
    ),
    path(
        'api/docs/',
        RedirectView.as_view(url='/api/docs/redoc/', permanent=False),
        name='api-docs-redirect',
    ),
    path(
        'api/docs',
        RedirectView.as_view(url='/api/docs/redoc/', permanent=False),
    ),
    path('favicon.ico', empty_favicon),
    # Suppress Chrome DevTools 404 warnings
    path('.well-known/appspecific/com.chrome.devtools.json', chrome_devtools_handler, name='chrome-devtools'),
]

if getattr(settings, 'ENABLE_SILK', False):
    urlpatterns.append(path('silk/', include('silk.urls', namespace='silk')))

from django.views.static import serve
from django.urls import re_path

# Debug toolbar and static media serving in non-production environments
is_production = os.getenv('DJANGO_ENV') == 'production'
if settings.DEBUG or not is_production:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
        
    # Only append static/media routes if the settings are configured
    if getattr(settings, 'MEDIA_URL', None) and getattr(settings, 'MEDIA_ROOT', None):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
        # Fallback for serving media files if static() helper doesn't work (e.g. some Channels configs)
        urlpatterns += [
            re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        ]