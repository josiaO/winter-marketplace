from django.urls import path, re_path

from sellers import views

app_name = 'sellers'

urlpatterns = [
    path('onboarding/progress/', views.OnboardingProgressView.as_view(), name='onboarding-progress'),
    path('store/setup/', views.StoreSetupView.as_view(), name='store-setup'),
    path('verification/identity/', views.IdentityVerificationSubmitView.as_view(), name='identity-submit'),
    path(
        'verification/identity/status/',
        views.IdentityVerificationStatusView.as_view(),
        name='identity-status',
    ),
    path('payout/add/', views.PayoutAddView.as_view(), name='payout-add'),
    path('payout/verify/', views.PayoutVerifyView.as_view(), name='payout-verify'),
    path('profile/', views.SellerProfileDashboardView.as_view(), name='seller-profile'),
    path(
        'verification/business/',
        views.BusinessVerificationSubmitView.as_view(),
        name='business-verification',
    ),
]

# Mounted at /api/admin/sellers/ via root URLconf (namespace sellers_admin).
admin_urlpatterns = [
    path(
        'verification-media/<str:token>/',
        views.AdminVerificationMediaView.as_view(),
        name='verification-media',
    ),
    # Optional trailing slash: some proxies/clients send .../verification-queue?page= (no slash before ?).
    re_path(
        r'^verification-queue/?$',
        views.AdminVerificationQueueListView.as_view(),
        name='verification-queue',
    ),
    re_path(
        r'^verifications/?$',
        views.AdminVerificationQueueListView.as_view(),
        name='verifications-queue',
    ),
    # Optional trailing slash on all pk routes: proxies/clients often drop the final / on POST.
    re_path(r'^(?P<pk>\d+)/?$', views.AdminSellerDetailView.as_view(), name='seller-detail'),
    re_path(
        r'^(?P<pk>\d+)/verification/identity/approve/?$',
        views.AdminIdentityApproveView.as_view(),
        name='identity-approve',
    ),
    re_path(
        r'^(?P<pk>\d+)/identity/approve/?$',
        views.AdminIdentityApproveView.as_view(),
        name='identity-approve-short',
    ),
    re_path(
        r'^(?P<pk>\d+)/verification/identity/reject/?$',
        views.AdminIdentityRejectView.as_view(),
        name='identity-reject',
    ),
    re_path(
        r'^(?P<pk>\d+)/identity/reject/?$',
        views.AdminIdentityRejectView.as_view(),
        name='identity-reject-short',
    ),
    re_path(
        r'^(?P<pk>\d+)/suspend/?$',
        views.AdminSellerSuspendView.as_view(),
        name='seller-suspend',
    ),
    re_path(
        r'^(?P<pk>\d+)/reinstate/?$',
        views.AdminSellerReinstateView.as_view(),
        name='seller-reinstate',
    ),
    re_path(
        r'^(?P<pk>\d+)/verification/business/approve/?$',
        views.AdminBusinessApproveView.as_view(),
        name='business-approve',
    ),
    re_path(
        r'^(?P<pk>\d+)/business/approve/?$',
        views.AdminBusinessApproveView.as_view(),
        name='business-approve-short',
    ),
    re_path(
        r'^(?P<pk>\d+)/verification/business/reject/?$',
        views.AdminBusinessRejectView.as_view(),
        name='business-reject',
    ),
    re_path(
        r'^(?P<pk>\d+)/business/reject/?$',
        views.AdminBusinessRejectView.as_view(),
        name='business-reject-short',
    ),
]
