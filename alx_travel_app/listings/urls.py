from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# Register your viewsets here if you have any

urlpatterns = [
    path('', include(router.urls)),
    
    # Property endpoints
    path('properties/', views.PropertyListCreateView.as_view(), name='property-list'),
    path('properties/<int:pk>/', views.PropertyRetrieveUpdateDestroyView.as_view(), name='property-detail'),
    
    # Booking endpoints
    path('bookings/', views.BookingListCreateView.as_view(), name='booking-list'),
    path('bookings/<int:pk>/', views.BookingRetrieveUpdateDestroyView.as_view(), name='booking-detail'),
    
    # Payment endpoints
    path('bookings/<int:booking_id>/pay/', views.initiate_payment, name='initiate-payment'),
    path('payments/<str:reference>/verify/', views.verify_payment, name='verify-payment'),
    path('payments/<int:payment_id>/status/', views.get_payment_status, name='payment-status'),
    path('api/payments/webhook/', views.chapa_webhook, name='chapa-webhook'),
    
    # User bookings
    path('user/bookings/', views.UserBookingsView.as_view(), name='user-bookings'),
    
    # Authentication endpoints
    path('auth/', include('rest_framework.urls')),
]