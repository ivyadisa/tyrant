from django.urls import path
from .views import (
    admin_list_users, admin_list_pending_users,
    admin_verify_user, admin_reject_user,
    admin_promote_user, admin_demote_user,
    admin_suspend_user, admin_unsuspend_user,
    admin_dashboard_analytics,
)

urlpatterns = [
    path('users', admin_list_users),
    path('users/pending', admin_list_pending_users),
    path('users/<uuid:user_id>/verify', admin_verify_user),
    path('users/<uuid:user_id>/reject', admin_reject_user),
    path('users/<uuid:user_id>/promote', admin_promote_user),
    path('users/<uuid:user_id>/demote', admin_demote_user),
    path('users/<uuid:user_id>/suspend', admin_suspend_user),
    path('users/<uuid:user_id>/unsuspend', admin_unsuspend_user),
    path('analytics', admin_dashboard_analytics),
]
