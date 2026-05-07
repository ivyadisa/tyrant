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
from .models import Wallet, WalletTransaction, PendingPayment
from .serializers import WalletSerializer, WalletTransactionSerializer
from .mpesa import stk_push
from .tasks import process_mpesa_callback
import json
import logging
from .utils import is_duplicate

logger = logging.getLogger(__name__)

BOOKING_AMOUNT = Decimal("10")

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

    def post(self, request, *args, **kwargs):
        try:
            phone = request.data.get("phone")
            unit_id = request.data.get("unit_id")
            amount = BOOKING_AMOUNT

            if not phone or not unit_id:
                return Response(
                    {"error": "Phone and unit_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check unit exists and is available
            from properties.models import Unit
            try:
                unit = Unit.objects.get(id=unit_id)
            except Unit.DoesNotExist:
                return Response(
                    {"error": "Unit not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Check no active booking exists
            from bookings.models import Booking
            has_active_booking = Booking.objects.filter(
                unit=unit,
                booking_status__in=["PENDING", "CONFIRMED", "PAID", "COMPLETED"],
            ).exists()
            if has_active_booking:
                return Response(
                    {"error": "Unit is already booked"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Prevent duplicate pending payment for same unit
            existing = PendingPayment.objects.filter(
                user=request.user,
                unit=unit,
            ).first()
            if existing:
                return Response(
                    {
                        "message": "Payment already initiated",
                        "checkout_request_id": existing.checkout_request_id,
                    },
                    status=status.HTTP_200_OK,
                )

            response = stk_push(phone, int(amount), settings.MPESA_CALLBACK_URL, str(unit_id))
            checkout_id = response.get("CheckoutRequestID")
            merchant_id = response.get("MerchantRequestID")

            if not checkout_id:
                return Response(
                    {"error": "STK push failed", "details": response},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Store intent — no booking yet
            PendingPayment.objects.create(
                user=request.user,
                unit=unit,
                phone_number=phone,
                amount=amount,
                checkout_request_id=checkout_id,
                merchant_request_id=merchant_id,
            )

            return Response(
                {
                    "message": "STK push initiated. Complete payment on your phone.",
                    "checkout_request_id": checkout_id,
                    "amount": str(amount),
                    "phone": phone,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"STK Push Error: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InitiateSubscriptionPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            phone = request.data.get("phone")
            apartment_id = request.data.get("apartment_id")
            amount = Decimal("10")

            if not phone:
                return Response(
                    {"error": "Phone number is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not apartment_id:
                logger.warning("Subscription initiated without apartment_id")

            from properties.models import Apartment
            apartment = None
            if apartment_id:
                try:
                    apartment = Apartment.objects.get(id=apartment_id)
                except Apartment.DoesNotExist:
                    return Response(
                        {"error": "Apartment not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # wallet/views.py — replace the existing_txn check in InitiateSubscriptionPaymentView

            from django.utils import timezone
            from datetime import timedelta

            wallet = get_or_create_wallet(request.user)

            # Only block if PENDING transaction is less than 5 minutes old
            # Older ones are considered abandoned (user ignored/dismissed the STK push)
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            existing_txn = WalletTransaction.objects.filter(
                wallet=wallet,
                transaction_type="SUBSCRIPTION",
                status="PENDING",
                created_at__gte=five_minutes_ago,
            ).first()

            if existing_txn:
                return Response(
                    {
                        "message": "Subscription payment already initiated",
                        "checkout_request_id": existing_txn.checkout_request_id,
                    },
                    status=status.HTTP_200_OK,
                )

            # Auto-expire any stale PENDING transactions before creating a new one
            WalletTransaction.objects.filter(
                wallet=wallet,
                transaction_type="SUBSCRIPTION",
                status="PENDING",
                created_at__lt=five_minutes_ago,
            ).update(status="FAILED")
            
            response = stk_push(
                phone, int(amount), settings.MPESA_CALLBACK_URL,
                str(apartment_id) if apartment_id else "general"
            )

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

            from .models import Subscription
            Subscription.objects.create(
                landlord=request.user,
                apartment=apartment,  # None is now allowed
                transaction=txn,
                status="PENDING",
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
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ----------------- M-Pesa Callback ----------------- #

@csrf_exempt
def mpesa_callback(request):
    if request.method != "POST":
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Only POST allowed"})

    try:
        data = json.loads(request.body)
        stk = data.get("Body", {}).get("stkCallback", {})
        checkout_id = stk.get("CheckoutRequestID")

        if is_duplicate(checkout_id):
            logger.warning(f"Duplicate callback ignored: {checkout_id}")
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Duplicate ignored"})

        # Check PendingPayment first (booking payments)
        pending = PendingPayment.objects.filter(checkout_request_id=checkout_id).first()

        # Fall back to WalletTransaction (subscription payments)
        if not pending:
            txn = WalletTransaction.objects.filter(checkout_request_id=checkout_id).first()
            if not txn:
                logger.warning(f"No record found for {checkout_id}")
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Ignored"})
            if txn.status == "COMPLETED":
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Already processed"})

        process_mpesa_callback.delay(stk)

        logger.info(f"MPESA callback received: {checkout_id}")
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})

    except Exception as e:
        logger.error(f"MPESA CALLBACK ERROR: {str(e)}", exc_info=True)
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Error handled"})

class SubscriptionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import Subscription
        has_active = Subscription.objects.filter(
            landlord=request.user,
            status="ACTIVE",
        ).exists()
        return Response({"has_active": has_active})