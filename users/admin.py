from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('id', 'username', 'email', 'role', 'status', 'verification_status')
    list_filter = ('role', 'status', 'verification_status')
    search_fields = ('username', 'email', 'phone_number')
    ordering = ('email',)
