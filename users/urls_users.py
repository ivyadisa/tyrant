from  django.urls import path

from .urls_auth import urlpatterns
from .views import (
    UserListView,
    user_profile,
    user_public_profile,
    UpdateUserProfileView,
)

urlpatterns = [
    path('', UserListView.as_view()),
    path('me', user_profile),
    path('me/update', UpdateUserProfileView.as_view()),
    path('<uuid:user_id>', user_public_profile),
]