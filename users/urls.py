from django.urls import path
from .views import RegisterView, CustomLoginView, UserListView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('list/', UserListView.as_view(), name='user-list'),
]
