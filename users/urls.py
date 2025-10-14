from django.urls import path
from .views import RegisterView, CustomLoginView, UserListView,  user_profile,  update_user_profile

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('list/', UserListView.as_view(), name='user-list'),
    path('profile/', user_profile, name='user-profile'),
    path('update/', update_user_profile, name='update-user-profile')
]
