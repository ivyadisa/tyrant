from django.contrib import admin
from .models import Notification, NotificationSetting


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "recipient", "type", "title", "is_read", "created_at"]
    list_filter = ["type", "is_read", "created_at"]
    search_fields = ["recipient__username", "title", "message"]
    readonly_fields = ["id", "created_at"]


@admin.register(NotificationSetting)
class NotificationSettingAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "email_enabled", "push_enabled"]
    search_fields = ["user__username"]