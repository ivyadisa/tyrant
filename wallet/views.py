from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.conf import settings
from bookings.models import Booking
from decimal import Decimal
from .models import Wallet, WalletTransaction
from .serializers import WalletSerializer, WalletTransactionSerializer, PaymentRequestSerializer
from .mpesa import stk_push
from .tasks import process_mpesa_callback
import json
import logging
from .utils import is_duplicate

logger = logging.getLogger(__name__)

BOOKING_AMOUNT = Decimal("1")

SAFE_MPESA_IPS = [
    "196.201.214.200",
    "196.201.214.206",
    "196.201.213.114",
    "196.201.214.207",
    "196.201.214.208",
]


# ----------------- Wallet Views ----------------- #

class WalletDetailView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
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
        except (TypeError, ValueError) as e:
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
                "transaction": WalletTransactionSerializer(transaction_obj).data,
            },
            status=status.HTTP_201_CREATED,
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
        except (TypeError, ValueError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if wallet.balance < amount:
            return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)

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
                "transaction": WalletTransactionSerializer(transaction_obj).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ----------------- STK Push View ----------------- #

class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentRequestSerializer

    def post(self, request, *args, **kwargs):
        try:
            phone = request.data.get("phone")
            booking_id = request.data.get("booking_id")
            amount = BOOKING_AMOUNT  # Fixed at KES 350

            if not phone or not booking_id:
                return Response(
                    {"error": "Phone and booking_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                booking = Booking.objects.get(id=booking_id, tenant=request.user)
            except Booking.DoesNotExist:
                return Response(
                    {"error": "Booking not found for this user"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if booking.booking_status in {"CANCELLED", "COMPLETED"}:
                return Response(
                    {"error": "Booking is not eligible for payment"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if booking.payment_status == "COMPLETED":
                return Response(
                    {"error": "Booking is already paid"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            wallet, _ = Wallet.objects.get_or_create(user=request.user)

            # INITIATION IDEMPOTENCY — prevent duplicate STK pushes for same booking
            existing_txn = WalletTransaction.objects.filter(
                wallet=wallet,
                booking_id=booking_id,
                status="PENDING",
            ).first()

            if existing_txn:
                logger.info(f"Duplicate payment prevented for booking {booking_id}")
                return Response(
                    {
                        "message": "Payment already initiated",
                        "checkout_request_id": existing_txn.checkout_request_id,
                    },
                    status=status.HTTP_200_OK,
                )

            response = stk_push(phone, int(amount), settings.MPESA_CALLBACK_URL, booking_id)

            checkout_id = response.get("CheckoutRequestID")
            merchant_id = response.get("MerchantRequestID")

            if not checkout_id:
                booking.payment_status = "FAILED"
                booking.booking_status = "CANCELLED"
                booking.save(update_fields=["payment_status", "booking_status", "updated_at"])
                return Response(
                    {"error": "STK push failed", "details": response},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="DEPOSIT",
                amount=amount,
                status="PENDING",
                checkout_request_id=checkout_id,
                merchant_request_id=merchant_id,
                phone_number=phone,
                booking=booking,
            )

            booking.payment_status = "PENDING"
            booking.save(update_fields=["payment_status", "updated_at"])

            logger.info(f"STK push initiated: {checkout_id}")

            return Response(
                {
                    "message": "STK push initiated successfully",
                    "checkout_request_id": checkout_id,
                    "merchant_request_id": merchant_id,
                    "amount": str(amount),
                    "phone": phone,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"STK Push Error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ----------------- M-Pesa Callback ----------------- #

@csrf_exempt
def mpesa_callback(request):
    if request.method != "POST":
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Only POST allowed"})

    # IP VALIDATION
    ip = request.META.get("REMOTE_ADDR")
    if ip not in SAFE_MPESA_IPS:
        logger.warning(f"Unauthorized MPESA callback from IP: {ip}")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Unauthorized IP"})

    try:
        data = json.loads(request.body)
        stk = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk.get("CheckoutRequestID")

        # CALLBACK IDEMPOTENCY — ignore duplicate callbacks
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