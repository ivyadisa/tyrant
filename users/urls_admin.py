from django.urls import path
from .views import (
    admin_list_users, admin_list_pending_users,
    admin_verify_user, admin_reject_user,
    admin_promote_user, admin_demote_user,
    admin_suspend_user, admin_unsuspend_user,
    admin_dashboard_analytics,
)

urlpatterns = [
    path('users/', admin_list_users, name='admin-users'),
    path('users/pending/', admin_list_pending_users, name='admin-users-pending'),
    path('users/<uuid:user_id>/verify/', admin_verify_user, name='admin-verify-user'),
    path('users/<uuid:user_id>/reject/', admin_reject_user, name='admin-reject-user'),
    path('users/<uuid:user_id>/promote/', admin_promote_user, name='admin-promote-user'),
    path('users/<uuid:user_id>/demote/', admin_demote_user, name='admin-demote-user'),
    path('users/<uuid:user_id>/suspend/', admin_suspend_user, name='admin-suspend-user'),
    path('users/<uuid:user_id>/unsuspend/', admin_unsuspend_user, name='admin-unsuspend-user'),
    path('analytics/', admin_dashboard_analytics, name='admin-analytics'),
]