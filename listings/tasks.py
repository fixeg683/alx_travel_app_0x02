from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_booking_confirmation_email(self, booking_id):
    """Send booking confirmation email"""
    try:
        from .models import Booking
        
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
        
        logger.info(f"Booking confirmation email sent for booking #{booking_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send confirmation email for booking #{booking_id}: {e}")
        # Retry the task after 5 minutes
        raise self.retry(exc=e, countdown=300)

@shared_task(bind=True, max_retries=3)
def send_payment_initiation_email(self, booking_id, checkout_url):
    """Send payment initiation email"""
    try:
        from .models import Booking
        
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
        
        logger.info(f"Payment initiation email sent for booking #{booking_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payment initiation email for booking #{booking_id}: {e}")
        raise self.retry(exc=e, countdown=300)

@shared_task(bind=True, max_retries=3)
def send_payment_failure_email(self, booking_id, failure_reason):
    """Send payment failure email"""
    try:
        from .models import Booking
        
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
        
        logger.info(f"Payment failure email sent for booking #{booking_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payment failure email for booking #{booking_id}: {e}")
        raise self.retry(exc=e, countdown=300)

@shared_task
def update_payment_status(payment_id):
    """Periodic task to update payment status"""
    try:
        from .models import Payment
        import requests
        from django.conf import settings
        
        payment = Payment.objects.get(id=payment_id)
        
        if payment.status != 'pending':
            return
        
        # Verify with Chapa API
        headers = {
            'Authorization': f'Bearer {settings.CHAPA_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        
        verify_url = f"https://api.chapa.co/v1/transaction/verify/{payment.reference}"
        response = requests.get(verify_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                payment.mark_as_success()
                logger.info(f"Payment #{payment_id} verified successfully")
            else:
                payment.mark_as_failed()
                logger.warning(f"Payment #{payment_id} verification failed")
        
    except Exception as e:
        logger.error(f"Failed to update payment status for #{payment_id}: {e}")