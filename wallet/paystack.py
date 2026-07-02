import requests
from django.conf import settings


def initialize_charge(email, amount, reference, callback_url=None):
    """
    Initialize a Paystack payment/charge.
    Returns the authorization URL for the payment page.
    """
    url = "https://api.paystack.co/transaction/initialize"

    if not callback_url:
        callback_url = settings.PAYSTACK_CALLBACK_URL

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "email": email,
        "amount": str(int(amount * 100)),  # Paystack expects amount in kobo (cents)
        "reference": reference,
        "callback_url": callback_url,
        "metadata": {
            "reference": reference,
        }
    }

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    print(f"PAYSTACK INITIALIZE: {response.status_code}")
    print(f"PAYSTACK RESPONSE: {data}")

    return data


def verify_transaction(reference):
    """
    Verify a Paystack transaction by reference.
    """
    url = f"https://api.paystack.co/transaction/verify/{reference}"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    response = requests.get(url, headers=headers)
    data = response.json()

    print(f"PAYSTACK VERIFY: {response.status_code}")
    print(f"PAYSTACK RESPONSE: {data}")

    return data


# ----------------- M-Pesa Direct (STK Push) via Paystack ----------------- #

def normalize_phone(phone):
    """Normalize phone number to international format (254xxxxxxxxx)."""
    phone = phone.replace("+", "").replace(" ", "").replace("-", "")

    if phone.startswith("0"):
        return "254" + phone[1:]
    if phone.startswith("7"):
        return "254" + phone
    if phone.startswith("254"):
        return phone
    # Default: assume it's already in international format
    return phone


def mpesa_direct_checkout(phone_number, amount, reference, callback_url=None):
    """
    Initialize M-Pesa Direct (STK Push) payment via Paystack.
    Triggers an STK push prompt to the customer's phone.

    Paystack M-Pesa Direct is available for Tanzania and other supported markets.
    """
    url = "https://api.paystack.co/mpesa/directcheckout"

    if not callback_url:
        callback_url = settings.PAYSTACK_CALLBACK_URL

    # Normalize phone to international format
    phone = normalize_phone(phone_number)

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "amount": str(int(amount)),  # Paystack M-Pesa expects full amount (not kobo)
        "currency": "KES",
        "phone": phone,
        "reference": reference,
        "callback_url": callback_url,
        "metadata": {
            "reference": reference,
        }
    }

    print(f"PAYSTACK MPESA DIRECT REQUEST: {payload}")

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()

    print(f"PAYSTACK MPESA DIRECT: {response.status_code}")
    print(f"PAYSTACK MPESA RESPONSE: {data}")

    return data


def verify_mpesa_transaction(reference):
    """
    Verify a Paystack M-Pesa transaction by reference.
    """
    url = f"https://api.paystack.co/mpesa/verify/{reference}"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    response = requests.get(url, headers=headers)
    data = response.json()

    print(f"PAYSTACK MPESA VERIFY: {response.status_code}")
    print(f"PAYSTACK MPESA VERIFY RESPONSE: {data}")

    return data