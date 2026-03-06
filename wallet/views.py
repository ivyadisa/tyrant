from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.conf import settings
from decimal import Decimal, InvalidOperation
from .models import Wallet, WalletTransaction
from .serializers import WalletSerializer, WalletTransactionSerializer, PaymentRequestSerializer
from .mpesa import stk_push
from .tasks import process_mpesa_callback
import json
import logging
from .utils import is_duplicate

logger = logging.getLogger(__name__)

SAFE_MPESA_IPS = [
    "196.201.214.200",
    "196.201.214.206",
    "196.201.213.114",
    "196.201.214.207",
    "196.201.214.208"
]


# ----------------- Wallet Views ----------------- #

class WalletDetailView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet


class WalletTransactionListView(generics.ListAPIView):
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


# ----------------- STK Push View ----------------- #

class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentRequestSerializer

    def post(self, request, *args, **kwargs):
        try:
            phone = request.data.get("phone")
            amount = Decimal(str(request.data.get("amount")))
            booking_id = request.data.get("booking_id")

            if not phone or not amount or not booking_id:
                return Response(
                    {"error": "Phone, amount, and booking_id are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            wallet, _ = Wallet.objects.get_or_create(user=request.user)

            #  INITIATION IDEMPOTENCY
            existing_txn = WalletTransaction.objects.filter(
                wallet=wallet,
                booking_id=booking_id,
                status="PENDING"
            ).first()

            if existing_txn:
                logger.info(f"Duplicate payment prevented for booking {booking_id}")
                return Response({
                    "message": "Payment already initiated",
                    "checkout_request_id": existing_txn.checkout_request_id
                }, status=status.HTTP_200_OK)

            callback_url = settings.MPESA_CALLBACK_URL

            try:
                response = stk_push(phone, float(amount), callback_url, booking_id)
            except TypeError as e:
                response = stk_push(phone, str(amount), callback_url, booking_id)

            checkout_id = response.get("CheckoutRequestID")
            merchant_id = response.get("MerchantRequestID")

            if not checkout_id:
                return Response({
                    "error": "STK push failed",
                    "details": response
                }, status=status.HTTP_400_BAD_REQUEST)

            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="DEPOSIT",
                amount=amount,
                status="PENDING",
                checkout_request_id=checkout_id,
                merchant_request_id=merchant_id,
                phone_number=phone,
                booking_id=booking_id
            )

            logger.info(f"STK push initiated: {checkout_id}")

            return Response({
                "message": "STK push initiated successfully",
                "checkout_request_id": checkout_id,
                "merchant_request_id": merchant_id,
                "amount": str(amount),
                "phone": phone
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"STK Push Error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ----------------- M-Pesa Callback ----------------- #

@csrf_exempt
def mpesa_callback(request):

    ip = request.META.get('REMOTE_ADDR')

    # IP VALIDATION
    if ip not in SAFE_MPESA_IPS:
        logger.warning(f"Unauthorized MPESA callback from IP: {ip}")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Unauthorized IP"})

    if request.method == "POST":
        try:
            data = json.loads(request.body)

            stk = data.get("Body", {}).get("stkCallback", {})
            checkout_id = stk.get("CheckoutRequestID")

            # CALLBACK IDEMPOTENCY
            if is_duplicate(checkout_id):
                logger.warning(f"Duplicate callback ignored: {checkout_id}")
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Duplicate ignored"})

            try:
                txn = WalletTransaction.objects.get(checkout_request_id=checkout_id)
            except WalletTransaction.DoesNotExist:
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Ignored"})

            if txn.status == "COMPLETED":
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Already processed"})

            # ASYNC PROCESSING
            process_mpesa_callback.delay(stk)

            logger.info(f"MPESA callback received: {checkout_id}")

            return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})

        except Exception as e:
            logger.error(f"MPESA CALLBACK ERROR: {str(e)}")
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Error handled"})

    return JsonResponse({"ResultCode": 1, "ResultDesc": "Only POST allowed"})