from django.contrib import admin
from .models import CablePlan, Customer, Bill, Payment, Notification

@admin.register(CablePlan)
class CablePlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'channels', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'plan', 'status', 'application_date')
    list_filter = ('status', 'application_date', 'plan')
    search_fields = ('user__username', 'user__email', 'phone')
    date_hierarchy = 'application_date'

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('customer', 'amount', 'bill_date', 'due_date', 'status')
    list_filter = ('status', 'bill_date', 'due_date')
    search_fields = ('customer__user__username', 'customer__user__email')
    date_hierarchy = 'bill_date'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('bill', 'amount', 'payment_method', 'payment_date', 'transaction_id')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('transaction_id', 'bill__customer__user__username')
    date_hierarchy = 'payment_date'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('customer', 'type', 'title', 'sent_date', 'is_read')
    list_filter = ('type', 'sent_date', 'is_read')
    search_fields = ('customer__user__username', 'title', 'message')
    date_hierarchy = 'sent_date'
