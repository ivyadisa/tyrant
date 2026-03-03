from celery import shared_task
import logging
from .models import WalletTransaction

logger = logging.getLogger("payments")

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5)
def process_mpesa_callback(self, stk_data):

    logger.info("Processing MPESA Callback")

    checkout_id = stk_data.get("CheckoutRequestID")
    result_code = stk_data.get("ResultCode")

    try:
        txn = WalletTransaction.objects.get(checkout_request_id=checkout_id)

        if result_code == 0:
            txn.status = "COMPLETED"
            txn.save()
            logger.info(f"Transaction completed: {checkout_id}")
        else:
            txn.status = "FAILED"
            txn.save()
            logger.warning(f"Transaction failed: {checkout_id}")

    except WalletTransaction.DoesNotExist:
        logger.error(f"Transaction not found: {checkout_id}")

    return "Processed"