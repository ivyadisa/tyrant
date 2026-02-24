from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from .models import Wallet, WalletTransaction
from .serializers import WalletSerializer, WalletTransactionSerializer
from decimal import Decimal, InvalidOperation

"""
    Wallet API (Deposit / Withdraw)
    
    Currently, this API simulates wallet deposits and withdrawals using internal balance updates.
    In the future, we might shift to handling real mobile money transactions either by:
    
    1. Integrating with a payment aggregator (e.g., Flutterwave, Paystack, DPO)
       - Aggregator handles Mpesa, Airtel Money, cards, etc.
       - Backend credits wallet only after receiving verified payment callbacks
    
    2. Listening directly from individual mobile money providers (e.g., Mpesa, Airtel Money)
       - Requires provider-specific API/webhook integrations
       - Backend updates wallet balance only after verifying transactions
    
    This API should be treated as a ledger for internal balance and testing purposes.
    Do NOT trust user input for real money deposits.
"""


class WalletDetailView(generics.RetrieveAPIView):
    """Get the authenticated user's wallet details"""
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet


class WalletTransactionListView(generics.ListAPIView):
    """List all wallet transactions for the user"""
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WalletTransaction.objects.filter(wallet__user=self.request.user)


class WalletDepositView(generics.CreateAPIView):
    """Handle wallet deposits"""
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)

        try:
            amount = Decimal(str(request.data.get("amount")))
            if amount <= 0:
                raise ValueError("Amount must be greater than zero")
        except (TypeError, ValueError, InvalidOperation) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            wallet.deposit(amount)
            transaction_obj = WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="DEPOSIT",
                amount=amount,
                status="COMPLETED",
            )

        return Response(
            {
                "message": "Deposit successful",
                "transaction": WalletTransactionSerializer(transaction_obj).data
            },
            status=status.HTTP_201_CREATED
        )


class WalletWithdrawView(generics.CreateAPIView):
    """Handle wallet withdrawals"""
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)

        try:
            amount = Decimal(str(request.data.get("amount")))
            if amount <= 0:
                raise ValueError("Amount must be greater than zero")
        except (TypeError, ValueError, InvalidOperation) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if wallet.balance < amount:
            return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)

        # Perform withdraw and transaction atomically
        with transaction.atomic():
            wallet.withdraw(amount)
            transaction_obj = WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="WITHDRAWAL",
                amount=amount,
                status="COMPLETED",
            )

        return Response(
            {
                "message": "Withdrawal successful",
                "transaction": WalletTransactionSerializer(transaction_obj).data
            },
            status=status.HTTP_201_CREATED
        )