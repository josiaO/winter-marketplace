from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserManagementViewSet, basename='user-management')
router.register(r'addresses', views.UserAddressViewSet, basename='address')
router.register(r'profile', views.UserProfileViewSet, basename='profile')

app_name = 'accounts'

auth_patterns = [
    path('auth/token/', views.MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', views.MyTokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', views.auth_logout, name='auth_logout'),
    path('auth/register/', views.register, name='register'),
    path('auth/signup/', views.signup, name='signup'),
    path('auth/routes/', views.get_user_routes, name='get_user_routes'),
    path('auth/<str:username>/activate/', views.activate, name='activate'),
    path('firebase-login/', views.firebase_login, name='firebase_login'),
    path('auth/password-reset/', views.PasswordResetView.as_view(), name='password_reset'),
    path('auth/password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    # OTP Endpoints
    path('otp/request/', views.request_otp, name='otp_request'),
    path('otp/verify/', views.verify_otp, name='otp_verify'),
    path('otp/change-password/', views.change_password_with_otp, name='otp_change_password'),
]

profile_patterns = [
    path('me/', views.user_profile, name='me'),
    path('profile/update/', views.update_user_profile, name='update_user_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    path('profile/become-seller/', views.upgrade_to_seller, name='become_seller'),
    # Legacy alias - redirect to become-seller
    path('profile/upgrade-to-agent/', views.upgrade_to_seller, name='upgrade_to_agent'),
]

urlpatterns = [
    *auth_patterns,
    *profile_patterns,
    path('', include(router.urls)),
]