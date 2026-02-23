import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(user, subject="Verify Your Email"):
    """
    Generates OTP, saves it, and sends email.
    """
    otp = generate_otp()

    user.email_otp = otp
    user.otp_expiry = timezone.now() + timedelta(minutes=10)
    user.save()

    send_mail(
        subject=subject,
        message=f"Your OTP is {otp}. It expires in 10 minutes.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def verify_user_otp(user, otp):
    """
    Validates OTP and expiry.
    """
    if user.email_otp != otp:
        return False, "Invalid OTP."

    if not user.otp_expiry or timezone.now() > user.otp_expiry:
        return False, "OTP expired."

    return True, "OTP valid."
