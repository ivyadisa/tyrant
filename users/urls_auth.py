from django.urls import path
from .views import (
    RegisterView, CustomLoginView,
    request_password_reset, confirm_password_reset,
    verify_email, resend_otp, verify_status,  csrf_token
)

urlpatterns = [
    path("csrf/", csrf_token),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('password-reset/request/', request_password_reset, name='password-reset-request'),
    path('password-reset/confirm/', confirm_password_reset, name='password-reset-confirm'),
    path('verify-email/', verify_email, name='verify-email'),
    path('resend-otp/', resend_otp, name='resend-otp'),
    path('verify-status/', verify_status, name='verify-status'),
]