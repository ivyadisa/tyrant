from celery import shared_task
import logging
from django.db import transaction
from .models import WalletTransaction

logger = logging.getLogger("payments")

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5)
def process_mpesa_callback(self, stk_data):

    logger.info("Processing MPESA Callback")

    checkout_id = stk_data.get("CheckoutRequestID")
    result_code = stk_data.get("ResultCode")

    try:
        txn = WalletTransaction.objects.get(checkout_request_id=checkout_id)

        with transaction.atomic():
            if result_code == 0:
                txn.status = "COMPLETED"
                txn.save(update_fields=["status"])

                if txn.booking:
                    txn.booking.payment_status = "COMPLETED"
                    txn.booking.booking_status = "PAID"
                    txn.booking.save(update_fields=["payment_status", "booking_status", "updated_at"])
                logger.info(f"Transaction completed: {checkout_id}")
            else:
                txn.status = "FAILED"
                txn.save(update_fields=["status"])

                if txn.booking:
                    txn.booking.payment_status = "FAILED"
                    txn.booking.booking_status = "CANCELLED"
                    txn.booking.save(update_fields=["payment_status", "booking_status", "updated_at"])
                logger.warning(f"Transaction failed: {checkout_id}")

    except WalletTransaction.DoesNotExist:
        logger.error(f"Transaction not found: {checkout_id}")

    return "Processed"