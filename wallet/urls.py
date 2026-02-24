from django.urls import path
from . import views

urlpatterns = [
    path("", views.WalletDetailView.as_view(), name="wallet-detail"),
    path("transactions/", views.WalletTransactionListView.as_view(), name="wallet-transactions"),
    path("deposit/", views.WalletDepositView.as_view(), name="wallet-deposit"),
    path("withdraw/", views.WalletWithdrawView.as_view(), name="wallet-withdraw"),
]
