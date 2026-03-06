from django.contrib import admin
from .models import Wallet, WalletTransaction

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "wallet_type", "balance", "currency", "created_at", "updated_at")
    search_fields = ("user__email", "user__username")
    list_filter = ("wallet_type", "currency", "created_at")
    ordering = ("-updated_at",)

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "transaction_type", "amount", "status", "created_at")
    list_filter = ("transaction_type", "status")
    search_fields = ("wallet__user__email", "wallet__user__username")
    ordering = ("-created_at",)
