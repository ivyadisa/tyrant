from celery import shared_task
import logging
from django.db import transaction
from django.utils import timezone


logger = logging.getLogger("payments")


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5)
def process_mpesa_callback(self, stk_data):
    from .models import PendingPayment, Wallet, WalletTransaction
    from bookings.models import Booking

    logger.info("Processing MPESA Callback")

    checkout_id = stk_data.get("CheckoutRequestID")
    result_code = stk_data.get("ResultCode")

    # Extract M-Pesa receipt number
    items = stk_data.get("CallbackMetadata", {}).get("Item", [])
    receipt = next((i["Value"] for i in items if i["Name"] == "MpesaReceiptNumber"), None)

    # --- Handle booking payment via PendingPayment ---
    pending = PendingPayment.objects.filter(checkout_request_id=checkout_id).first()
    if pending:
        if result_code != 0:
            logger.warning(f"Booking payment failed for {checkout_id}")
            pending.delete()
            return "Failed"

        with transaction.atomic():
            booking = Booking.objects.create(
                tenant=pending.user,
                landlord=pending.unit.apartment.landlord,
                unit=pending.unit,
                booking_status="PENDING",
                payment_status="COMPLETED",
                booking_amount=pending.amount,
            )

            wallet, _ = Wallet.objects.get_or_create(
                user=pending.user,
                defaults={"wallet_type": "PLATFORM"}
            )

            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="DEPOSIT",
                amount=pending.amount,
                status="COMPLETED",
                checkout_request_id=checkout_id,
                phone_number=pending.phone_number,
                mpesa_receipt_number=receipt,
                booking=booking,
            )

            pending.delete()

        logger.info(f"Booking {booking.id} created after successful payment {checkout_id}")
        return "Booking Created"

    # wallet/tasks.py — full corrected subscription section

    # --- Handle subscription payment via WalletTransaction ---
    txn = WalletTransaction.objects.filter(checkout_request_id=checkout_id).first()
    if txn:
        with transaction.atomic():
            if result_code == 0:
                from django.utils import timezone
                from datetime import timedelta

                txn.status = "COMPLETED"
                txn.mpesa_receipt_number = receipt
                txn.save(update_fields=["status", "mpesa_receipt_number"])
                txn.wallet.deposit(txn.amount)

                # Activate subscription — 30 days from now
                sub = getattr(txn, "subscription", None)
                if sub:
                    sub.status = "ACTIVE"
                    sub.expires_at = timezone.now() + timedelta(days=30)
                    sub.save(update_fields=["status", "expires_at", "updated_at"])

                    # Use apartment_id instead of sub.apartment to avoid
                    # RelatedObjectDoesNotExist when apartment is NULL
                    if sub.apartment_id:
                        sub.apartment.is_approved = True
                        sub.apartment.save(update_fields=["is_approved"])

                logger.info(f"Subscription activated for {checkout_id}")
            else:
                txn.status = "FAILED"
                txn.save(update_fields=["status"])

                sub = getattr(txn, "subscription", None)
                if sub:
                    sub.status = "FAILED"
                    sub.save(update_fields=["status", "updated_at"])

                logger.warning(f"Subscription payment failed: {checkout_id}")

        return "Processed"


def expire_subscriptions():
    from .models import Subscription
    from properties.models import Apartment

    expired = Subscription.objects.filter(
        status="ACTIVE",
        expires_at__lt=timezone.now()
    )
    for sub in expired:
        sub.status = "EXPIRED"
        sub.save(update_fields=["status", "updated_at"])

        # Same fix — guard with apartment_id not sub.apartment
        if sub.apartment_id:
            sub.apartment.is_approved = False
            sub.apartment.save(update_fields=["is_approved"])

def expire_stale_pending_transactions():
    """Mark PENDING transactions older than 10 minutes as FAILED."""
    from .models import WalletTransaction
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(minutes=10)
    stale = WalletTransaction.objects.filter(
        status="PENDING",
        created_at__lt=cutoff,
    )
    count = stale.update(status="FAILED")
    logger.info(f"Expired {count} stale pending transactions")