import uuid
import json
import logging
from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from .models import Wallet, WalletTransaction, PendingPayment
from .serializers import WalletSerializer, WalletTransactionSerializer
from .intasend import stk_push, check_status
from .tasks import process_intasend_webhook
from .utils import is_duplicate

logger = logging.getLogger(__name__)

BOOKING_AMOUNT = Decimal("10")   # KES 500 — change to your actual amount


def get_or_create_wallet(user):
    role = getattr(user, "role", "").upper()
    wallet_type = "LANDLORD" if role == "LANDLORD" else "PLATFORM"
    wallet, created = Wallet.objects.get_or_create(
        user=user,
        defaults={"wallet_type": wallet_type}
    )
    if created:
        logger.info(f"Wallet created for user {user.id} type={wallet_type}")
    return wallet


# ── Wallet Views ──────────────────────────────────────────────────────────────

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
        return WalletTransaction.objects.filter(wallet=wallet)


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
            txn = WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="DEPOSIT",
                amount=amount,
                status="COMPLETED",
            )

        return Response(
            {"message": "Deposit successful", "transaction": WalletTransactionSerializer(txn).data},
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
            txn = WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="WITHDRAWAL",
                amount=amount,
                status="COMPLETED",
            )

        return Response(
            {"message": "Withdrawal successful", "transaction": WalletTransactionSerializer(txn).data},
            status=status.HTTP_201_CREATED,
        )


# ── STK Push — Booking Payment ────────────────────────────────────────────────

class InitiatePaymentView(APIView):
    """Tenant pays to book a unit via M-Pesa STK Push."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        phone = request.data.get("phone") or request.data.get("phone_number")
        unit_id = request.data.get("unit_id")
        amount = BOOKING_AMOUNT

        if not phone or not unit_id:
            return Response(
                {"error": "phone and unit_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from properties.models import Unit
            unit = Unit.objects.get(id=unit_id)
        except Unit.DoesNotExist:
            return Response({"error": "Unit not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check 1: unit status — RESERVED or OCCUPIED means taken
        if unit.status in ("RESERVED", "OCCUPIED"):
            return Response(
                {"error": "This unit is no longer available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check 2: active booking already exists
        has_active = Booking.objects.filter(
            unit=unit,
            booking_status__in=["PENDING", "CONFIRMED", "PAID", "COMPLETED"],
            payment_status__in=["PENDING", "COMPLETED"],
        ).exists()
        if has_active:
            return Response(
                {"error": "This unit is already booked."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check 3: another tenant already has a pending payment for this unit
        five_min_ago = timezone.now() - timedelta(minutes=5)
        other_pending = PendingPayment.objects.filter(
            unit=unit,
            created_at__gte=five_min_ago,
        ).exclude(user=request.user).first()
        if other_pending:
            return Response(
                {"error": "Another tenant is currently completing payment for this unit. Please try again shortly."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check 4: same tenant duplicate within 5 minutes
        existing = PendingPayment.objects.filter(
            user=request.user,
            unit=unit,
            created_at__gte=five_min_ago,
        ).first()
        if existing:
            return Response(
                {"message": "Payment already initiated", "invoice_id": existing.checkout_request_id},
                status=status.HTTP_200_OK,
            )

        # Expire stale pending payments for this tenant on this unit
        PendingPayment.objects.filter(
            user=request.user,
            unit=unit,
            created_at__lt=five_min_ago,
        ).update(status="FAILED")

        try:
            response = stk_push(
                phone_number=phone,
                amount=int(amount),
                narrative="Tyrent Homes - Unit Booking",
            )
        except Exception as e:
            logger.error(f"IntaSend STK Push error: {e}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        invoice = response.get("invoice", {})
        invoice_id = invoice.get("invoice_id") or invoice.get("id")

        if not invoice_id:
            logger.error(f"No invoice_id in IntaSend response: {response}")
            return Response(
                {"error": "STK push failed", "details": response},
                status=status.HTTP_400_BAD_REQUEST,
            )

        PendingPayment.objects.create(
            user=request.user,
            unit=unit,
            phone_number=phone,
            amount=amount,
            checkout_request_id=invoice_id,
        )

        return Response(
            {
                "message": "STK push sent. Enter your M-Pesa PIN to complete.",
                "invoice_id": invoice_id,
                "amount": str(amount),
                "phone": phone,
            },
            status=status.HTTP_200_OK,
        )


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        invoice_id = request.query_params.get("invoice_id")
        if not invoice_id:
            return Response({"error": "invoice_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            response = check_status(invoice_id)
            invoice = response.get("invoice", {})
            state = invoice.get("state", "PENDING")

            if state == "COMPLETE":
                from .models import PendingPayment, Wallet, WalletTransaction
                from bookings.models import Booking

                pending = PendingPayment.objects.filter(
                    checkout_request_id=invoice_id
                ).first()

                if pending:
                    existing = Booking.objects.filter(
                        unit=pending.unit,
                        payment_status="COMPLETED",
                    ).first()

                    if not existing:
                        with transaction.atomic():
                            mpesa_ref = invoice.get("mpesa_reference") or invoice.get("provider_ref", "")

                            booking = Booking.objects.create(
                                tenant=pending.user,
                                landlord=pending.unit.apartment.landlord,
                                unit=pending.unit,
                                booking_status="PENDING",
                                payment_status="COMPLETED",
                                booking_amount=pending.amount,
                                move_in_date=timezone.now().date(),
                            )

                            # Reserve the unit immediately
                            pending.unit.status = "RESERVED"
                            pending.unit.save(update_fields=["status", "last_status_updated"])
                            pending.unit.apartment.recalc_unit_counts()

                            wallet, _ = Wallet.objects.get_or_create(
                                user=pending.user,
                                defaults={"wallet_type": "PLATFORM"}
                            )

                            WalletTransaction.objects.create(
                                wallet=wallet,
                                transaction_type="DEPOSIT",
                                amount=pending.amount,
                                status="COMPLETED",
                                checkout_request_id=invoice_id,
                                phone_number=pending.phone_number,
                                mpesa_receipt_number=mpesa_ref,
                                booking=booking,
                            )

                            pending.delete()
                            logger.info(f"Booking {booking.id} created and unit {pending.unit.id} reserved: {invoice_id}")

            return Response({
                "invoice_id": invoice_id,
                "state": state,
                "details": invoice
            })

        except Exception as e:
            logger.error(f"Status check error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── STK Push — Subscription Payment ──────────────────────────────────────────

class InitiateSubscriptionPaymentView(APIView):
    """Landlord pays subscription via M-Pesa STK Push."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        phone = request.data.get("phone") or request.data.get("phone_number")
        apartment_id = request.data.get("apartment_id")
        amount = Decimal("500")   # KES 500 subscription fee

        if not phone:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not apartment_id:
            logger.warning("Subscription initiated without apartment_id")

        apartment = None
        if apartment_id:
            from properties.models import Apartment
            try:
                apartment = Apartment.objects.get(id=apartment_id)
            except Apartment.DoesNotExist:
                return Response({"error": "Apartment not found"}, status=status.HTTP_404_NOT_FOUND)

        wallet = get_or_create_wallet(request.user)

        # Block duplicate within 5 minutes
        five_min_ago = timezone.now() - timedelta(minutes=5)
        existing_txn = WalletTransaction.objects.filter(
            wallet=wallet,
            transaction_type="SUBSCRIPTION",
            status="PENDING",
            created_at__gte=five_min_ago,
        ).first()

        if existing_txn:
            return Response(
                {"message": "Subscription payment already initiated", "invoice_id": existing_txn.checkout_request_id},
                status=status.HTTP_200_OK,
            )

        # Expire stale
        WalletTransaction.objects.filter(
            wallet=wallet,
            transaction_type="SUBSCRIPTION",
            status="PENDING",
            created_at__lt=five_min_ago,
        ).update(status="FAILED")

        try:
            response = stk_push(
                phone_number=phone,
                amount=int(amount),
                narrative="Tyrent Homes - Property Listing Subscription",
            )
        except Exception as e:
            logger.error(f"IntaSend subscription STK Push error: {e}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        invoice = response.get("invoice", {})
        invoice_id = invoice.get("invoice_id") or invoice.get("id")

        if not invoice_id:
            logger.error(f"No invoice_id in IntaSend response: {response}")
            return Response(
                {"error": "STK push failed", "details": response},
                status=status.HTTP_400_BAD_REQUEST,
            )

        txn = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="SUBSCRIPTION",
            amount=amount,
            status="PENDING",
            checkout_request_id=invoice_id,
            phone_number=phone,
        )

        from .models import Subscription
        Subscription.objects.create(
            landlord=request.user,
            apartment=apartment,
            transaction=txn,
            status="PENDING",
        )

        logger.info(f"Subscription STK Push sent: invoice_id={invoice_id}")

        return Response(
            {
                "message": "STK push sent. Enter your M-Pesa PIN to complete.",
                "invoice_id": invoice_id,
                "amount": str(amount),
                "phone": phone,
            },
            status=status.HTTP_200_OK,
        )


# ── Subscription Status ───────────────────────────────────────────────────────

class SubscriptionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import Subscription
        has_active = Subscription.objects.filter(
            landlord=request.user,
            status="ACTIVE",
        ).exists()
        return Response({"has_active": has_active})


# ── IntaSend Webhook ──────────────────────────────────────────────────────────

@csrf_exempt
def intasend_webhook(request):
    """Receives IntaSend payment notifications."""
    if request.method != "POST":
        return JsonResponse({"status": "error"}, status=405)

    try:
        data = json.loads(request.body)
        logger.info(f"IntaSend webhook received: {data}")

        # Verify challenge
        challenge = data.get("challenge")
        if settings.INTASEND_WEBHOOK_CHALLENGE and challenge != settings.INTASEND_WEBHOOK_CHALLENGE:
            logger.warning("Invalid IntaSend webhook challenge")
            return JsonResponse({"status": "error", "message": "Invalid challenge"}, status=403)

        invoice_id = (
            data.get("invoice_id")
            or data.get("invoice", {}).get("invoice_id")
            or data.get("invoice", {}).get("id")
        )

        if not invoice_id:
            logger.warning(f"No invoice_id in webhook: {data}")
            return JsonResponse({"status": "ignored"})

        if is_duplicate(invoice_id):
            logger.warning(f"Duplicate webhook ignored: {invoice_id}")
            return JsonResponse({"status": "duplicate"})

        # Queue for processing
        process_intasend_webhook.delay(data)

        return JsonResponse({"status": "accepted"})

    except Exception as e:
        logger.error(f"IntaSend webhook error: {e}", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)