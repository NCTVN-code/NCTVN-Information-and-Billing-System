from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class CablePlan(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    channels = models.IntegerField()
    features = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Customer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disconnected', 'Disconnected'),
    ]
    
    TIME_SLOT_CHOICES = [
        ('morning', 'Morning (9 AM - 12 PM)'),
        ('afternoon', 'Afternoon (1 PM - 4 PM)'),
        ('evening', 'Evening (4 PM - 7 PM)'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(CablePlan, on_delete=models.SET_NULL, null=True, blank=True)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    application_date = models.DateTimeField(auto_now_add=True)
    installation_date = models.DateField(null=True, blank=True)
    installation_time = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES, null=True, blank=True)
    installation_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Plan history fields
    previous_plans = models.JSONField(default=list, blank=True, help_text="List of previous plans with dates and reasons")
    plan_start_date = models.DateTimeField(auto_now_add=True, help_text="Start date of current plan")
    plan_change_reason = models.TextField(blank=True, help_text="Reason for last plan change")

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.status}"

    def add_to_plan_history(self, old_plan, reason=None):
        """Add current plan to history when changing plans"""
        if old_plan:
            history_entry = {
                'plan_id': old_plan.id,
                'plan_name': old_plan.name,
                'price': str(old_plan.price),
                'channels': old_plan.channels,
                'start_date': self.plan_start_date.isoformat(),
                'end_date': timezone.now().isoformat(),
                'reason': reason or self.plan_change_reason,
                'status': self.status
            }
            
            if not self.previous_plans:
                self.previous_plans = []
            
            self.previous_plans.insert(0, history_entry)
            self.plan_start_date = timezone.now()
            self.plan_change_reason = reason or ''

class Bill(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue')
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    bill_date = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid', db_index=True)
    payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    reminder_notification_sent = models.BooleanField(default=False)
    overdue_notification_sent = models.BooleanField(default=False)
    warning_notification_sent = models.BooleanField(default=False)
    disconnection_notification_sent = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'bill_date']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['bill_date', 'status']),
        ]

    def __str__(self):
        return f"Bill for {self.customer.user.get_full_name()} - {self.bill_date}"

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('gcash', 'GCash'),
        ('stripe', 'Stripe')
    ]

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_date = models.DateTimeField(auto_now_add=True, db_index=True)
    transaction_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['payment_date', 'amount']),
            models.Index(fields=['bill', 'payment_date']),
        ]

    def __str__(self):
        return f"Payment for {self.bill.customer.user.get_full_name()} - {self.payment_date}"

class Notification(models.Model):
    TYPE_CHOICES = [
        ('application', 'Application Status'),
        ('payment', 'Payment Confirmation'),
        ('overdue', 'Overdue Notice'),
        ('disconnection', 'Disconnection Warning')
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    sent_date = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.type} notification for {self.customer.user.get_full_name()}"
