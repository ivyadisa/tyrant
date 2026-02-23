from django.urls import  path

from wallet.urls import urlpatterns
from .views import (
    RegisterView, CustomLoginView,
    request_password_reset, confirm_password_reset, verify_status
)

urlpatterns = [
    path('register', RegisterView.as_view()),
    path('login', CustomLoginView.as_view()),
    path('password-reset/request', request_password_reset),
    path('password-reset/confirm', confirm_password_reset),

    #Email Verification
    path('verify-email/', verify_email, name='verify-email'),
    path('resend-otp/', resend_otp, name='resend-otp'),
    path('verify-status/', verify_status, name='verify-status'),
]