# listings/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from .booking import Booking  # Assuming you have a Booking model

class Payment(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]
    
    booking = models.OneToOneField(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='payment'
    )
    transaction_id = models.CharField(max_length=100, unique=True)
    chapa_transaction_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, 
        choices=PAYMENT_STATUS, 
        default='pending'
    )
    currency = models.CharField(max_length=3, default='ETB')
    payment_method = models.CharField(max_length=50, blank=True)
    customer_email = models.EmailField()
    customer_first_name = models.CharField(max_length=100)
    customer_last_name = models.CharField(max_length=100)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Additional fields for Chapa
    checkout_url = models.URLField(blank=True)
    reference = models.CharField(max_length=100, unique=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment {self.reference} - {self.status}"
    
    def mark_as_success(self):
        self.status = 'success'
        self.verified_at = timezone.now()
        self.save()
    
    def mark_as_failed(self):
        self.status = 'failed'
        self.save()
    
    def is_successful(self):
        return self.status == 'success'
