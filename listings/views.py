# listings/views.py
import requests
import json
import uuid
from datetime import datetime
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from celery import shared_task

from .models import Payment, Booking
from .serializers import PaymentSerializer, BookingSerializer

# Chapa API Configuration
CHAPA_SECRET_KEY = settings.CHAPA_SECRET_KEY
CHAPA_BASE_URL = 'https://api.chapa.co/v1'
CHAPA_INITIATE_URL = f'{CHAPA_BASE_URL}/transaction/initialize'
CHAPA_VERIFY_URL = f'{CHAPA_BASE_URL}/transaction/verify/'

def generate_reference():
    """Generate unique reference for payment"""
    return f"TX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request, booking_id):
    """
    Initiate payment for a booking
    """
    try:
        # Get booking
        booking = Booking.objects.get(id=booking_id, user=request.user)
        
        # Check if payment already exists
        if hasattr(booking, 'payment') and booking.payment:
            return Response({
                'error': 'Payment already initiated for this booking'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate unique reference
        reference = generate_reference()
        
        # Prepare payment data for Chapa
        payment_data = {
            'amount': str(booking.total_price),
            'currency': 'ETB',
            'email': request.user.email,
            'first_name': request.user.first_name or 'Customer',
            'last_name': request.user.last_name or 'User',
            'phone_number': request.user.phone or '0900000000',
            'tx_ref': reference,
            'callback_url': f"{settings.BASE_URL}/api/payments/verify/",
            'return_url': f"{settings.FRONTEND_URL}/booking/{booking.id}/status",
            'customization': {
                'title': 'ALX Travel App',
                'description': f'Payment for booking #{booking.id}',
            }
        }
        
        # Headers for Chapa API
        headers = {
            'Authorization': f'Bearer {CHAPA_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Make request to Chapa API
        try:
            response = requests.post(
                CHAPA_INITIATE_URL,
                json=payment_data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            chapa_response = response.json()
            
            if chapa_response.get('status') == 'success':
                # Create payment record
                payment = Payment.objects.create(
                    booking=booking,
                    amount=booking.total_price,
                    currency='ETB',
                    customer_email=request.user.email,
                    customer_first_name=request.user.first_name or 'Customer',
                    customer_last_name=request.user.last_name or 'User',
                    reference=reference,
                    checkout_url=chapa_response['data']['checkout_url'],
                    transaction_id=chapa_response['data']['tx_ref'],
                    chapa_transaction_id=chapa_response['data']['reference']
                )
                
                # Send payment initiation email (async)
                send_payment_initiation_email.delay(
                    booking.id,
                    payment.checkout_url
                )
                
                return Response({
                    'status': 'success',
                    'message': 'Payment initiated successfully',
                    'checkout_url': payment.checkout_url,
                    'payment_id': payment.id,
                    'reference': payment.reference
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Failed to initiate payment with Chapa',
                    'details': chapa_response
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to payment gateway',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
    except Booking.DoesNotExist:
        return Response({
            'error': 'Booking not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': 'An error occurred',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@require_POST
def chapa_webhook(request):
    """
    Webhook endpoint for Chapa payment notifications
    """
    try:
        # Get the webhook data
        data = json.loads(request.body)
        
        # Verify the webhook signature (if implemented by Chapa)
        # This depends on Chapa's webhook implementation
        
        transaction_ref = data.get('tx_ref')
        chapa_transaction_id = data.get('reference')
        status = data.get('status')
        
        if not transaction_ref:
            return JsonResponse({'error': 'No transaction reference'}, status=400)
        
        # Find the payment
        try:
            payment = Payment.objects.get(reference=transaction_ref)
            
            if status == 'success':
                payment.mark_as_success()
                payment.chapa_transaction_id = chapa_transaction_id
                payment.save()
                
                # Update booking status
                booking = payment.booking
                booking.status = 'confirmed'
                booking.save()
                
                # Send confirmation email (async)
                send_booking_confirmation_email.delay(booking.id)
                
            elif status in ['failed', 'canceled']:
                payment.status = status
                payment.save()
                
                # Update booking status
                booking = payment.booking
                booking.status = 'cancelled'
                booking.save()
                
                # Send failure email (async)
                send_payment_failure_email.delay(booking.id, status)
            
            return JsonResponse({'status': 'success'})
            
        except Payment.DoesNotExist:
            return JsonResponse({'error': 'Payment not found'}, status=404)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_payment(request, reference):
    """
    Verify payment status manually
    """
    try:
        payment = Payment.objects.get(
            reference=reference,
            booking__user=request.user
        )
        
        # If already verified, return current status
        if payment.is_successful():
            return Response({
                'status': 'success',
                'payment': PaymentSerializer(payment).data,
                'booking': BookingSerializer(payment.booking).data
            })
        
        # Verify with Chapa API
        headers = {
            'Authorization': f'Bearer {CHAPA_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        
        try:
            verify_url = f"{CHAPA_VERIFY_URL}{payment.chapa_transaction_id or payment.reference}"
            response = requests.get(verify_url, headers=headers, timeout=30)
            response.raise_for_status()
            verify_data = response.json()
            
            if verify_data.get('status') == 'success':
                payment.mark_as_success()
                payment.chapa_transaction_id = verify_data['data'].get('reference', '')
                payment.save()
                
                # Update booking
                booking = payment.booking
                booking.status = 'confirmed'
                booking.save()
                
                # Send confirmation email
                send_booking_confirmation_email.delay(booking.id)
                
                return Response({
                    'status': 'success',
                    'message': 'Payment verified successfully',
                    'payment': PaymentSerializer(payment).data,
                    'booking': BookingSerializer(payment.booking).data
                })
            else:
                payment.mark_as_failed()
                return Response({
                    'status': 'failed',
                    'message': 'Payment verification failed',
                    'payment': PaymentSerializer(payment).data
                })
                
        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to verify payment',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
    except Payment.DoesNotExist:
        return Response({
            'error': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_status(request, payment_id):
    """
    Get payment status
    """
    try:
        payment = Payment.objects.get(
            id=payment_id,
            booking__user=request.user
        )
        
        return Response({
            'payment': PaymentSerializer(payment).data,
            'checkout_url': payment.checkout_url if payment.status == 'pending' else None
        })
        
    except Payment.DoesNotExist:
        return Response({
            'error': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)

# Celery tasks for email sending
@shared_task
def send_booking_confirmation_email(booking_id):
    """Send booking confirmation email"""
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        
        booking = Booking.objects.get(id=booking_id)
        user = booking.user
        
        subject = f"Booking Confirmation - #{booking.id}"
        html_content = render_to_string('emails/booking_confirmation.html', {
            'booking': booking,
            'user': user
        })
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        return True
    except Exception as e:
        print(f"Failed to send confirmation email: {e}")
        return False

@shared_task
def send_payment_initiation_email(booking_id, checkout_url):
    """Send payment initiation email"""
    try:
        booking = Booking.objects.get(id=booking_id)
        user = booking.user
        
        subject = f"Complete Your Payment - Booking #{booking.id}"
        html_content = render_to_string('emails/payment_initiation.html', {
            'booking': booking,
            'user': user,
            'checkout_url': checkout_url
        })
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        return True
    except Exception as e:
        print(f"Failed to send payment initiation email: {e}")
        return False

@shared_task
def send_payment_failure_email(booking_id, failure_reason):
    """Send payment failure email"""
    try:
        booking = Booking.objects.get(id=booking_id)
        user = booking.user
        
        subject = f"Payment Failed - Booking #{booking.id}"
        html_content = render_to_string('emails/payment_failure.html', {
            'booking': booking,
            'user': user,
            'failure_reason': failure_reason
        })
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        return True
    except Exception as e:
        print(f"Failed to send payment failure email: {e}")
        return False