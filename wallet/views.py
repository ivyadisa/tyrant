from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Wallet, WalletTransaction
from .serializers import WalletSerializer, WalletTransactionSerializer

class WalletDetailView(generics.RetrieveAPIView):
    """Get the authenticated user's wallet details"""
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return Wallet.objects.get(user=self.request.user)


class WalletTransactionListView(generics.ListAPIView):
    """List all wallet transactions for the user"""
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WalletTransaction.objects.filter(wallet__user=self.request.user)


class WalletWithdrawView(generics.CreateAPIView):
    """Handle wallet withdrawals"""
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        wallet = Wallet.objects.get(user=request.user)
        amount = float(request.data.get("amount"))

        if wallet.balance < amount:
            return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)

        wallet.withdraw(amount)

        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="WITHDRAWAL",
            amount=amount,
            status="COMPLETED",
        )

        return Response(
            {"message": "Withdrawal successful", "transaction": WalletTransactionSerializer(transaction).data},
            status=status.HTTP_201_CREATED,
        )


class WalletDepositView(generics.CreateAPIView):
    """Simulate wallet deposits (e.g. from payment callbacks)"""
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        wallet = Wallet.objects.get(user=request.user)
        amount = float(request.data.get("amount"))

        wallet.deposit(amount)

        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="DEPOSIT",
            amount=amount,
            status="COMPLETED",
        )

        return Response(
            {"message": "Deposit successful", "transaction": WalletTransactionSerializer(transaction).data},
            status=status.HTTP_201_CREATED,
        )
