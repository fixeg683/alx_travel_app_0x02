from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Payment, Booking
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Payment)
def handle_payment_status_change(sender, instance, created, **kwargs):
    """Handle payment status changes"""
    if created:
        logger.info(f"New payment created: {instance.reference}")
        return
    
    # Check if status has changed
    try:
        old_instance = Payment.objects.get(pk=instance.pk)
    except Payment.DoesNotExist:
        return
    
    if old_instance.status != instance.status:
        logger.info(f"Payment {instance.reference} status changed from {old_instance.status} to {instance.status}")
        
        # Update booking status based on payment status
        if instance.status == 'success':
            instance.booking.status = 'confirmed'
            instance.booking.save()
            logger.info(f"Booking #{instance.booking.id} confirmed due to successful payment")
            
        elif instance.status == 'failed':
            instance.booking.status = 'cancelled'
            instance.booking.save()
            logger.info(f"Booking #{instance.booking.id} cancelled due to failed payment")

@receiver(pre_save, sender=Booking)
def validate_booking_dates(sender, instance, **kwargs):
    """Validate booking dates before saving"""
    if instance.check_in and instance.check_out:
        if instance.check_in >= instance.check_out:
            raise ValueError("Check-in date must be before check-out date")
        
        # Check if property is available for the dates
        overlapping_bookings = Booking.objects.filter(
            property=instance.property,
            check_in__lt=instance.check_out,
            check_out__gt=instance.check_in,
            status__in=['pending', 'confirmed']
        ).exclude(id=instance.id)
        
        if overlapping_bookings.exists():
            raise ValueError("Property is not available for the selected dates")