from celery import shared_task
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .paystack import verify_transaction
from .intasend import check_status, normalize_phone, stk_push, get_service


logger = logging.getLogger("payments")


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5)
def process_paystack_callback(self, reference):
    """Process Paystack payment callback."""
    from .models import PendingPayment, Wallet, WalletTransaction
    from bookings.models import Booking

    logger.info(f"Processing Paystack callback for reference: {reference}")

    try:
        # Verify the transaction with Paystack
        response = verify_transaction(reference)
        if not response.get("status"):
            logger.error(f"Paystack verification failed: {response}")
            return "Failed"

        data = response.get("data", {})
        status = data.get("status")

        if status != "success":
            logger.warning(f"Paystack transaction not successful: {status}")
            # Mark pending payment as failed
            pending = PendingPayment.objects.filter(checkout_request_id=reference).first()
            if pending:
                pending.delete()
            return "Failed"

        amount_paid = data.get("amount", 0) / 100  # Convert from kobo to main currency

        # Check PendingPayment first (booking payments)
        pending = PendingPayment.objects.filter(checkout_request_id=reference).first()
        if pending:
            with transaction.atomic():
                booking = Booking.objects.create(
                    tenant=pending.user,
                    landlord=pending.unit.apartment.landlord,
                    unit=pending.unit,
                    booking_status="PENDING",
                    payment_status="COMPLETED",
                    booking_amount=pending.amount,
                    move_in_date=timezone.now().date(),
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
                    checkout_request_id=reference,
                    phone_number=pending.phone_number,
                    booking=booking,
                )

                pending.delete()

            logger.info(f"Booking {booking.id} created after successful payment {reference}")
            return "Booking Created"

        # Fall back to WalletTransaction (subscription payments)
        txn = WalletTransaction.objects.filter(checkout_request_id=reference).first()
        if txn:
            with transaction.atomic():
                txn.status = "COMPLETED"
                txn.save(update_fields=["status"])
                txn.wallet.deposit(txn.amount)

                # Activate subscription — 30 days from now
                sub = getattr(txn, "subscription", None)
                if sub:
                    sub.status = "ACTIVE"
                    sub.expires_at = timezone.now() + timedelta(days=30)
                    sub.save(update_fields=["status", "expires_at", "updated_at"])

                    if sub.apartment_id:
                        sub.apartment.is_approved = True
                        sub.apartment.save(update_fields=["is_approved"])

                logger.info(f"Subscription activated for {reference}")
            return "Processed"

        logger.warning(f"No record found for reference: {reference}")
        return "Ignored"

    except Exception as e:
        logger.error(f"Paystack callback error: {str(e)}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5)
def process_mpesa_callback(self, stk_data):
    from .models import PendingPayment, Wallet, WalletTransaction
    from bookings.models import Booking

    logger.info("Processing MPESA Callback")

    checkout_id = stk_data.get("CheckoutRequestID")
    result_code = stk_data.get("ResultCode")

    result_code = int(result_code) if result_code is not None else -1

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
                move_in_date=timezone.now().date(),
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

    # --- Handle subscription payment via WalletTransaction ---
    txn = WalletTransaction.objects.filter(checkout_request_id=checkout_id).first()
    if txn:
        with transaction.atomic():
            if result_code == 0:
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


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5)
def process_intasend_webhook(self, data):
    from .models import PendingPayment, Wallet, WalletTransaction
    from bookings.models import Booking
    from django.utils import timezone
    from datetime import timedelta

    logger.info(f"Processing IntaSend webhook: {data}")

    invoice = data.get("invoice", {})
    invoice_id = invoice.get("invoice_id") or invoice.get("id") or data.get("invoice_id")
    state = invoice.get("state") or data.get("state", "")
    mpesa_ref = invoice.get("mpesa_reference") or invoice.get("provider_reference")

    is_success = state == "COMPLETE"

    # --- Booking payment ---
    pending = PendingPayment.objects.filter(checkout_request_id=invoice_id).first()
    if pending:
        if not is_success:
            logger.warning(f"Booking payment failed: {invoice_id}")
            pending.status = "FAILED"
            pending.save(update_fields=["status"])
            return "Failed"

        with transaction.atomic():
            booking = Booking.objects.create(
                tenant=pending.user,
                landlord=pending.unit.apartment.landlord,
                unit=pending.unit,
                booking_status="PENDING",
                payment_status="COMPLETED",
                booking_amount=pending.amount,
                move_in_date=timezone.now().date(),
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
                checkout_request_id=invoice_id,
                phone_number=pending.phone_number,
                mpesa_receipt_number=mpesa_ref,
                booking=booking,
            )
            pending.delete()

        logger.info(f"Booking {booking.id} created: {invoice_id}")
        return "Booking Created"

    # --- Subscription payment ---
    txn = WalletTransaction.objects.filter(checkout_request_id=invoice_id).first()
    if txn:
        with transaction.atomic():
            if is_success:
                txn.status = "COMPLETED"
                txn.mpesa_receipt_number = mpesa_ref
                txn.save(update_fields=["status", "mpesa_receipt_number"])
                txn.wallet.deposit(txn.amount)

                sub = getattr(txn, "subscription", None)
                if sub:
                    sub.status = "ACTIVE"
                    sub.expires_at = timezone.now() + timedelta(days=30)
                    sub.save(update_fields=["status", "expires_at", "updated_at"])
                    if sub.apartment_id:
                        sub.apartment.is_approved = True
                        sub.apartment.save(update_fields=["is_approved"])

                logger.info(f"Subscription activated: {invoice_id}")
            else:
                txn.status = "FAILED"
                txn.save(update_fields=["status"])
                sub = getattr(txn, "subscription", None)
                if sub:
                    sub.status = "FAILED"
                    sub.save(update_fields=["status", "updated_at"])
                logger.warning(f"Subscription payment failed: {invoice_id}")

        return "Processed"

    logger.warning(f"No record found for invoice_id: {invoice_id}")
    return "Ignored"


def expire_subscriptions():
    from .models import Subscription

    expired = Subscription.objects.filter(
        status="ACTIVE",
        expires_at__lt=timezone.now()
    )
    for sub in expired:
        sub.status = "EXPIRED"
        sub.save(update_fields=["status", "updated_at"])

        if sub.apartment_id:
            sub.apartment.is_approved = False
            sub.apartment.save(update_fields=["is_approved"])


def expire_stale_pending_transactions():
    """Mark PENDING transactions older than 10 minutes as FAILED."""
    from .models import WalletTransaction

    cutoff = timezone.now() - timedelta(minutes=10)
    stale = WalletTransaction.objects.filter(
        status="PENDING",
        created_at__lt=cutoff,
    )
    count = stale.update(status="FAILED")
    logger.info(f"Expired {count} stale pending transactions")