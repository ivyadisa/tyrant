from intasend import APIService
from django.conf import settings
import logging

logger = logging.getLogger("payments")


def get_service():
    return APIService(
        token=settings.INTASEND_SECRET_KEY,
        publishable_key=settings.INTASEND_PUBLISHABLE_KEY,
        test=settings.INTASEND_TEST_MODE,
    )


def normalize_phone(phone):
    phone = str(phone).replace("+", "").replace(" ", "").replace("-", "")
    if phone.startswith("0"):
        return "254" + phone[1:]
    if phone.startswith("7") or phone.startswith("1"):
        return "254" + phone
    return phone


def stk_push(phone_number, amount, narrative="Tyrent Homes Payment"):
    """
    Initiates M-Pesa STK Push via IntaSend SDK.
    Returns the full response dict.
    """
    phone = normalize_phone(phone_number)
    service = get_service()

    logger.info(f"IntaSend STK Push → phone={phone}, amount={amount}")

    response = service.collect.mpesa_stk_push(
        phone_number=phone,
        email=None,
        amount=int(amount),
        narrative=narrative,
    )

    logger.info(f"IntaSend STK Push response: {response}")
    return response


def check_status(invoice_id):
    """Check payment status by invoice_id."""
    service = get_service()
    response = service.collect.status(invoice_id=invoice_id)
    logger.info(f"IntaSend status check [{invoice_id}]: {response}")
    return response