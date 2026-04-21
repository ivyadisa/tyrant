from  django.urls import path

from .urls_auth import urlpatterns
from .views import UserListView, user_profile, update_user_profile, user_public_profile

urlpatterns = [
    path('', UserListView.as_view()),
    path('me', user_profile),
    path('me/update', update_user_profile),
    path('<uuid:user_id>', user_public_profile),
]