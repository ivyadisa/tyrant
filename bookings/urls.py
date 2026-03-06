from django.urls import path
from . import views

urlpatterns = [
    path("", views.BookingCreateView.as_view(), name="create-booking"),
    path("tenants/", views.TenantBookingListView.as_view(), name="tenant-bookings"),
    path("landlords/", views.LandlordBookingListView.as_view(), name="landlord-bookings"),
    path("<uuid:pk>/", views.BookingDetailView.as_view(), name="booking-detail"),
    path("<uuid:pk>/cancel/", views.BookingCancelView.as_view(), name="cancel-booking"),
]
