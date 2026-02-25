from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Wallet, WalletTransaction
from .serializers import WalletSerializer, WalletTransactionSerializer
from bookings.models import Booking
from .mpesa import stk_push
import json

# ----------------- Wallet Views ----------------- #

class WalletDetailView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return Wallet.objects.get(user=self.request.user)


class WalletTransactionListView(generics.ListAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WalletTransaction.objects.filter(wallet__user=self.request.user)


class WalletWithdrawView(generics.CreateAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        wallet = Wallet.objects.get(user=request.user)
        amount = float(request.data.get("amount"))

        if wallet.balance < amount:
            return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)

        wallet.withdraw(amount)

        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="WITHDRAWAL",
            amount=amount,
            status="COMPLETED",
        )

        return Response(
            {"message": "Withdrawal successful", "transaction": WalletTransactionSerializer(transaction).data},
            status=status.HTTP_201_CREATED,
        )


class WalletDepositView(generics.CreateAPIView):
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        wallet = Wallet.objects.get(user=request.user)
        amount = float(request.data.get("amount"))

        wallet.deposit(amount)

        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="DEPOSIT",
            amount=amount,
            status="COMPLETED",
        )

        return Response(
            {"message": "Deposit successful", "transaction": WalletTransactionSerializer(transaction).data},
            status=status.HTTP_201_CREATED,
        )


# ----------------- STK Push View ----------------- #

class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            phone = request.data.get("phone")
            amount = request.data.get("amount")
            booking_id = request.data.get("booking_id")  

            if not phone or not amount or not booking_id:
                return Response({"error": "Phone, amount, and booking_id are required"}, status=status.HTTP_400_BAD_REQUEST)

            # Trigger STK Push and include booking_id in callback
            callback_url = f"{request.build_absolute_uri('/wallet/mpesa/callback/')}?booking_id={booking_id}"
            response = stk_push(phone, amount, callback_url, booking_id)

            return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ----------------- M-Pesa Callback ----------------- #

@csrf_exempt
def mpesa_callback(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            print("M-Pesa Callback Data:", data)

            result_code = data.get("Body", {}).get("stkCallback", {}).get("ResultCode")
            result_desc = data.get("Body", {}).get("stkCallback", {}).get("ResultDesc")
            callback_metadata = data.get("Body", {}).get("stkCallback", {}).get("CallbackMetadata", {}).get("Item", [])

            amount = 0
            phone = None
            mpesa_receipt = None

            for item in callback_metadata:
                if item.get("Name") == "Amount":
                    amount = float(item.get("Value"))
                elif item.get("Name") == "MpesaReceiptNumber":
                    mpesa_receipt = item.get("Value")
                elif item.get("Name") == "PhoneNumber":
                    phone = str(item.get("Value"))

            if result_code == 0 and phone:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(profile__phone_number=phone)
                    wallet = Wallet.objects.get(user=user)
                    wallet.deposit(amount)

                    # Get booking_id from query params
                    booking_id = request.GET.get("booking_id")
                    booking = None
                    if booking_id:
                        try:
                            booking = Booking.objects.get(id=booking_id)
                            booking.payment_status = "COMPLETED"
                            booking.booking_status = "PAID"
                            booking.paid_on = timezone.now()
                            booking.save()
                        except Booking.DoesNotExist:
                            print(f"No booking found with id {booking_id}")

                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type="DEPOSIT",
                        amount=amount,
                        status="COMPLETED",
                        mpesa_receipt_number=mpesa_receipt,
                        description=f"M-Pesa payment for booking {booking_id}" if booking else "M-Pesa payment",
                        booking=booking
                    )

                except User.DoesNotExist:
                    print(f"No user found with phone {phone}")
                except Wallet.DoesNotExist:
                    print(f"No wallet found for user with phone {phone}")

            return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})

        except json.JSONDecodeError:
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid JSON"}, status=400)
        except Exception as e:
            print("Callback Error:", e)
            return JsonResponse({"ResultCode": 1, "ResultDesc": str(e)}, status=500)
    else:
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Only POST allowed"}, status=405)