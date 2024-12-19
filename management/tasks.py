from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Bill, Notification, Customer
from datetime import timedelta
from django_q.tasks import async_task

def check_bills():
    """Main task that triggers all bill checks"""
    print(f"Processing bill notifications at {timezone.now()}")
    async_task(notify_upcoming_due_bills)
    async_task(update_overdue_bills)
    async_task(send_disconnection_warnings)
    async_task(handle_service_disconnections)

def notify_upcoming_due_bills():
    """Send reminders for bills due tomorrow"""
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    due_tomorrow_bills = Bill.objects.filter(
        due_date=tomorrow,
        status='unpaid',
        reminder_notification_sent=False
    ).select_related('customer', 'customer__user')

    for bill in due_tomorrow_bills:
        # Create notification
        Notification.objects.create(
            customer=bill.customer,
            type='payment',
            title='Bill Due Tomorrow',
            message=f'Your bill of ₱{bill.amount} is due tomorrow. Please settle your payment to avoid service interruption.'
        )

        # Send email
        send_mail(
            subject='Bill Payment Reminder',
            message=f"""Dear {bill.customer.user.get_full_name()},

This is a reminder that your cable TV bill of ₱{bill.amount} is due tomorrow, {bill.due_date.strftime('%B %d, %Y')}.

Please settle your payment to avoid any service interruption.

Best regards,
Kabacan Northwest Cable TV Network""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[bill.customer.user.email],
            fail_silently=True,
        )

        # Mark as notified
        bill.reminder_notification_sent = True
        bill.save()

def update_overdue_bills():
    """Update bill status to overdue and notify customers"""
    today = timezone.now().date()
    
    due_today_bills = Bill.objects.filter(
        due_date=today,
        status='unpaid',
        overdue_notification_sent=False
    ).select_related('customer', 'customer__user')

    for bill in due_today_bills:
        # Update bill status to overdue
        bill.status = 'overdue'
        bill.overdue_notification_sent = True
        bill.save()

        # Create notification
        Notification.objects.create(
            customer=bill.customer,
            type='overdue',
            title='Bill Overdue',
            message=f'Your bill of ₱{bill.amount} is now overdue. Please settle your payment immediately to avoid service disconnection.'
        )

        # Send email
        send_mail(
            subject='Bill Payment Overdue',
            message=f"""Dear {bill.customer.user.get_full_name()},

Your cable TV bill of ₱{bill.amount} is now overdue.

Please settle your payment immediately to avoid service disconnection.

Best regards,
Kabacan Northwest Cable TV Network""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[bill.customer.user.email],
            fail_silently=True,
        )

def send_disconnection_warnings():
    """Send final warning before service disconnection"""
    today = timezone.now().date()
    one_day_past = today - timedelta(days=1)
    
    one_day_overdue_bills = Bill.objects.filter(
        due_date=one_day_past,
        status='overdue',
        warning_notification_sent=False
    ).select_related('customer', 'customer__user')

    for bill in one_day_overdue_bills:
        # Create notification
        Notification.objects.create(
            customer=bill.customer,
            type='disconnection',
            title='Final Payment Warning',
            message=f'Your bill of ₱{bill.amount} is 1 day overdue. Service will be disconnected tomorrow if payment is not received.'
        )

        # Send email
        send_mail(
            subject='Final Payment Warning',
            message=f"""Dear {bill.customer.user.get_full_name()},

This is a final warning regarding your overdue cable TV bill of ₱{bill.amount}.

Your service will be disconnected tomorrow if payment is not received.

Best regards,
Kabacan Northwest Cable TV Network""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[bill.customer.user.email],
            fail_silently=True,
        )

        # Mark as notified
        bill.warning_notification_sent = True
        bill.save()

def handle_service_disconnections():
    """Process automatic service disconnections for overdue bills"""
    today = timezone.now().date()
    two_days_past = today - timedelta(days=2)
    
    two_days_overdue_bills = Bill.objects.filter(
        due_date=two_days_past,
        status='overdue',
        disconnection_notification_sent=False
    ).select_related('customer', 'customer__user')

    for bill in two_days_overdue_bills:
        # Update customer status to disconnected
        customer = bill.customer
        customer.status = 'disconnected'
        customer.save()

        # Create notification
        Notification.objects.create(
            customer=customer,
            type='disconnection',
            title='Service Disconnected',
            message=f'Your service has been disconnected due to non-payment of ₱{bill.amount}. Please settle your bill to restore service.'
        )

        # Send email
        send_mail(
            subject='Service Disconnected',
            message=f"""Dear {customer.user.get_full_name()},

Your cable TV service has been disconnected due to non-payment of ₱{bill.amount}.

To restore your service, please settle your outstanding balance and contact our customer service.

Best regards,
Kabacan Northwest Cable TV Network""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.user.email],
            fail_silently=True,
        )

        # Mark as notified
        bill.disconnection_notification_sent = True
        bill.save()