import uuid
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


def get_or_create_wallet(user):
    """Helper to always create wallet with correct wallet_type based on user role."""
    role = getattr(user, "role", "").upper()
    wallet_type = "LANDLORD" if role == "LANDLORD" else "PLATFORM"
    wallet, created = Wallet.objects.get_or_create(
        user=user,
        defaults={"wallet_type": wallet_type}
    )
    if created:
        logger.info(f"Wallet created for user {user.id} type={wallet_type}")
    return wallet


# ----------------- Wallet Views ----------------- #

class WalletDetailView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return get_or_create_wallet(self.request.user)


class WalletTransactionListView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        wallet = get_or_create_wallet(self.request.user)
        logger.info(f"Fetching transactions for wallet {wallet.id}, user {self.request.user.id}")
        txns = WalletTransaction.objects.filter(wallet=wallet)
        logger.info(f"Found {txns.count()} transactions")
        return txns


class WalletDepositView(generics.CreateAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        wallet = get_or_create_wallet(request.user)

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
        wallet = get_or_create_wallet(request.user)

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
            amount = BOOKING_AMOUNT

            if not phone or not booking_id:
                return Response(
                    {"error": "Phone and booking_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate UUID
            try:
                uuid.UUID(str(booking_id))
            except ValueError:
                return Response(
                    {"error": "booking_id must be a valid UUID"},
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

            wallet = get_or_create_wallet(request.user)

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

            txn = WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="DEPOSIT",
                amount=amount,
                status="PENDING",
                checkout_request_id=checkout_id,
                merchant_request_id=merchant_id,
                phone_number=phone,
                booking=booking,
            )
            logger.info(f"Booking payment transaction created: {txn.id}")

            booking.payment_status = "PENDING"
            booking.save(update_fields=["payment_status", "updated_at"])

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
            logger.error(f"STK Push Error: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InitiateSubscriptionPaymentView(APIView):
    """Handles M-Pesa STK push for property listing subscriptions."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            phone = request.data.get("phone")
            apartment_id = request.data.get("apartment_id")
            amount = Decimal("500")

            if not phone:
                return Response(
                    {"error": "Phone number is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            wallet = get_or_create_wallet(request.user)
            logger.info(f"Subscription payment for wallet {wallet.id}, user {request.user.id}")

            # Prevent duplicate pending subscription
            existing_txn = WalletTransaction.objects.filter(
                wallet=wallet,
                transaction_type="SUBSCRIPTION",
                status="PENDING",
            ).first()

            if existing_txn:
                logger.info(f"Existing pending subscription: {existing_txn.id}")
                return Response(
                    {
                        "message": "Subscription payment already initiated",
                        "checkout_request_id": existing_txn.checkout_request_id,
                    },
                    status=status.HTTP_200_OK,
                )

            response = stk_push(
                phone,
                int(amount),
                settings.MPESA_CALLBACK_URL,
                apartment_id or "subscription",
            )
            logger.info(f"STK push response: {response}")

            checkout_id = response.get("CheckoutRequestID")
            merchant_id = response.get("MerchantRequestID")

            if not checkout_id:
                return Response(
                    {"error": "STK push failed", "details": response},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            txn = WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="SUBSCRIPTION",
                amount=amount,
                status="PENDING",
                checkout_request_id=checkout_id,
                merchant_request_id=merchant_id,
                phone_number=phone,
            )
            logger.info(f"Subscription transaction created: {txn.id}")

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
            logger.error(f"Subscription STK Push Error: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ----------------- M-Pesa Callback ----------------- #

@csrf_exempt
def mpesa_callback(request):
    if request.method != "POST":
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Only POST allowed"})

    # IP VALIDATION — commented out for development/testing
    # ip = request.META.get("REMOTE_ADDR")
    # if ip not in SAFE_MPESA_IPS:
    #     logger.warning(f"Unauthorized MPESA callback from IP: {ip}")
    #     return JsonResponse({"ResultCode": 1, "ResultDesc": "Unauthorized IP"})

    try:
        data = json.loads(request.body)
        stk = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk.get("CheckoutRequestID")

        if is_duplicate(checkout_id):
            logger.warning(f"Duplicate callback ignored: {checkout_id}")
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Duplicate ignored"})

        try:
            txn = WalletTransaction.objects.get(checkout_request_id=checkout_id)
        except WalletTransaction.DoesNotExist:
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Ignored"})

        if txn.status == "COMPLETED":
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Already processed"})

        process_mpesa_callback.delay(stk)

        logger.info(f"MPESA callback received: {checkout_id}")
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})

    except Exception as e:
        logger.error(f"MPESA CALLBACK ERROR: {str(e)}", exc_info=True)
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Error handled"})