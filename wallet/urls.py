from django.urls import path
from . import views

urlpatterns = [
    path("", views.WalletDetailView.as_view(), name="wallet-detail"),
    path("transactions/", views.WalletTransactionListView.as_view(), name="wallet-transactions"),
    path("deposit/", views.WalletDepositView.as_view(), name="wallet-deposit"),
    path("withdraw/", views.WalletWithdrawView.as_view(), name="wallet-withdraw"),
    path("pay/", views.InitiatePaymentView.as_view(), name="wallet-pay"),
    path("subscription/", views.InitiateSubscriptionPaymentView.as_view(), name="wallet-subscription"),
    path("subscription/status/", views.SubscriptionStatusView.as_view(), name="subscription-status"),
    path("mpesa/callback/", views.mpesa_callback, name="mpesa-callback"),
]