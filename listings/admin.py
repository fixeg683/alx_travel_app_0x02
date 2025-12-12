from django.contrib import admin
from .models import Property, Booking, Payment
from django.utils.html import format_html
from django.utils import timezone

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'booking_link', 'amount', 'currency', 
                    'status_badge', 'customer_email', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('reference', 'customer_email', 'transaction_id')
    readonly_fields = ('reference', 'transaction_id', 'chapa_transaction_id', 
                      'created_at', 'updated_at', 'verified_at')
    fieldsets = (
        ('Payment Information', {
            'fields': ('booking', 'reference', 'transaction_id', 'chapa_transaction_id')
        }),
        ('Amount & Status', {
            'fields': ('amount', 'currency', 'status')
        }),
        ('Customer Information', {
            'fields': ('customer_email', 'customer_first_name', 'customer_last_name')
        }),
        ('Chapa Details', {
            'fields': ('checkout_url', 'payment_method')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'verified_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'success': 'green',
            'failed': 'red',
            'canceled': 'gray'
        }
        color = colors.get(obj.status, 'blue')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def booking_link(self, obj):
        url = f"/admin/listings/booking/{obj.booking.id}/change/"
        return format_html('<a href="{}">Booking #{}</a>', url, obj.booking.id)
    booking_link.short_description = 'Booking'

class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'property', 'user', 'check_in', 'check_out', 
                    'status_badge', 'total_price', 'created_at')
    list_filter = ('status', 'property', 'check_in', 'check_out')
    search_fields = ('user__username', 'user__email', 'property__title')
    readonly_fields = ('created_at', 'updated_at')
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'confirmed': 'green',
            'cancelled': 'red',
            'completed': 'blue'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

# Register models
admin.site.register(Property)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Payment, PaymentAdmin)