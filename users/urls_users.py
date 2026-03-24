from django.urls import path
from .views import UserListView, user_profile, update_user_profile

urlpatterns = [
    path('', UserListView.as_view(), name='user-list'),
    path('me/', user_profile, name='user-profile'),
    path('me/update/', update_user_profile, name='user-update-profile'),
]