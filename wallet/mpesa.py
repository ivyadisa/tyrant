import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings
import base64
from datetime import datetime

def normalize_phone(phone):
    phone = phone.replace("+", "")

    if phone.startswith("0"):
        return "254" + phone[1:]
    if phone.startswith("7"):
        return "254" + phone
    return phone


def get_access_token():
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(
        url,
        auth=HTTPBasicAuth(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET)
    )
    return response.json().get("access_token")


def stk_push(phone_number, amount, callback_url=None, booking_id=None):
    phone_number = normalize_phone(phone_number)

    access_token = get_access_token()
    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    data_to_encode = settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + timestamp
    password = base64.b64encode(data_to_encode.encode()).decode()

    headers = {"Authorization": f"Bearer {access_token}"}

    if not callback_url:
        callback_url = settings.MPESA_CALLBACK_URL

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": "Tyrent",
        "TransactionDesc": "House Booking Payment"
    }

    response = requests.post(url, json=payload, headers=headers)
    print("MPESA RESPONSE:", response.status_code, response.json())  # ← this line
    print("STK STATUS:", response.status_code)
    print("STK RAW:", response.text)
    return response.json()