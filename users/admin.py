from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    list_display = (
        'id',
        'username',
        'email',
        'role',
        'status',
        'verification_status',
        'is_verified_button',
    )

    list_filter = ('role', 'status', 'verification_status')
    search_fields = ('username', 'email', 'phone_number')
    ordering = ('email',)

    # 👇 This makes it editable in the table
    list_editable = ('verification_status',)

    # Optional: show a clickable "button-like" action
    def is_verified_button(self, obj):
        if obj.verification_status == User.VERIF_VERIFIED:
            return "✅ Verified"
        elif obj.verification_status == User.VERIF_REJECTED:
            return "❌ Rejected"
        return "⏳ Pending"

    is_verified_button.short_description = "Verification"