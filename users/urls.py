from django.urls import path
from .views import (
    RegisterView, CustomLoginView, UserListView,
    user_profile, update_user_profile,
    admin_list_users, admin_list_pending_users,
    admin_verify_user, admin_reject_user,
    landlord_dashboard, tenant_dashboard,
    admin_promote_user, admin_demote_user,
    admin_suspend_user, admin_unsuspend_user,
    admin_dashboard_analytics,
    request_password_reset, confirm_password_reset
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('list/', UserListView.as_view(), name='user-list'),
    path('profile/', user_profile, name='user-profile'),
    path('update/', update_user_profile, name='update-user-profile'),

    # Admin routes
    path('admin/list/', admin_list_users, name='admin-list-users'),
    path('admin/pending/', admin_list_pending_users, name='admin-list-pending-users'),
    path('admin/verify/<uuid:user_id>/', admin_verify_user, name='admin-verify-user'),
    path('admin/reject/<uuid:user_id>/', admin_reject_user, name='admin-reject-user'),
    path('admin/promote/<uuid:user_id>/', admin_promote_user, name='admin-promote-user'),
    path('admin/demote/<uuid:user_id>/', admin_demote_user, name='admin-demote-user'),
    path('admin/suspend/<uuid:user_id>/', admin_suspend_user, name='admin-suspend-user'),
    path('admin/unsuspend/<uuid:user_id>/', admin_unsuspend_user, name='admin-unsuspend-user'),
    path('admin/analytics/', admin_dashboard_analytics, name='admin-analytics'),

    # Landlord & Tenant
    path('landlord/dashboard/', landlord_dashboard, name='landlord-dashboard'),
    path('tenant/dashboard/', tenant_dashboard, name='tenant-dashboard'),

    # Password Reset
    path('password-reset/request/', request_password_reset, name='password-reset-request'),
    path('password-reset/confirm/', confirm_password_reset, name='password-reset-confirm'),
]
