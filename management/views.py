from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction  # Add this import at the top
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import CablePlan, Customer, Bill, Payment, Notification


def login_view(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            login(request, user)

            if not remember:
                request.session.set_expiry(0)  # Session expires when browser closes

            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')


@login_required(login_url='admin_login')
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('admin_login')


@login_required(login_url='admin_login')
def view_profile(request):
    user = request.user
    context = {
        'user': user,
        'total_customers': Customer.objects.count(),
        'total_revenue': Payment.objects.aggregate(total=Sum('amount'))['total'] or 0,
        'recent_activities': get_recent_activities(),
    }
    return render(request, 'view_profile.html', context)


@login_required(login_url='admin_login')
def edit_profile(request):
    user = request.user

    if request.method == 'POST':
        # Basic Information
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')

        # Change Password
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if current_password and new_password:
            if user.check_password(current_password):
                if new_password == confirm_password:
                    user.set_password(new_password)
                    messages.success(request, 'Password updated successfully.')
                else:
                    messages.error(request, 'New passwords do not match.')
                    return redirect('edit_admin_profile')
            else:
                messages.error(request, 'Current password is incorrect.')
                return redirect('edit_admin_profile')

        # # Profile Picture
        # if 'profile_picture' in request.FILES:
        #     profile_pic = request.FILES['profile_picture']
        #     # Define allowed extensions
        #     allowed_extensions = ['.jpg', '.jpeg', '.png']
        #     # Get file extension
        #     _, ext = os.path.splitext(profile_pic.name)
        #     if ext.lower() not in allowed_extensions:
        #         messages.error(request, 'Invalid file type. Please upload a JPG or PNG image.')
        #         return redirect('edit_admin_profile')
        #
        #     # Save the file
        #     file_path = f'media/profile_pics/{user.username}{ext}'
        #     with open(file_path, 'wb+') as destination:
        #         for chunk in profile_pic.chunks():
        #             destination.write(chunk)
        #     user.profile_picture = f'profile_pics/{user.username}{ext}'

        user.save()

        # If password was changed, update the session
        if new_password:
            update_session_auth_hash(request, user)

        messages.success(request, 'Profile updated successfully.')
        return redirect('view_admin_profile')

    return render(request, 'edit_profile.html', {'user': user})


def get_recent_activities():
    # Get last 10 activities
    activities = []

    # Add recent customer applications
    recent_applications = Customer.objects.filter(
        status='pending'
    ).order_by('-application_date')[:5]
    for app in recent_applications:
        activities.append({
            'type': 'application',
            'date': app.application_date,
            'message': f'New application from {app.user.get_full_name()}'
        })

    # Add recent payments
    recent_payments = Payment.objects.select_related(
        'bill', 'bill__customer'
    ).order_by('-payment_date')[:5]
    for payment in recent_payments:
        activities.append({
            'type': 'payment',
            'date': payment.payment_date,
            'message': f'Payment received from {payment.bill.customer.user.get_full_name()}'
        })

    # Add recent notifications
    recent_notifications = Notification.objects.select_related(
        'customer'
    ).order_by('-sent_date')[:5]
    for notif in recent_notifications:
        activities.append({
            'type': 'notification',
            'date': notif.sent_date,
            'message': f'Notification sent to {notif.customer.user.get_full_name()}'
        })

    # Sort all activities by date
    activities.sort(key=lambda x: x['date'], reverse=True)
    return activities[:10]  # Return only the 10 most recent activities


@login_required(login_url='admin_login')
def admin_dashboard(request):
    # Existing statistics
    total_customers = Customer.objects.count()
    active_customers = Customer.objects.filter(status='approved').count()
    pending_applications = Customer.objects.filter(status='pending').count()
    total_revenue = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0

    # Get recent data
    recent_applications = Customer.objects.filter(
        status='pending'
    ).order_by('-application_date')[:5]

    recent_payments = Payment.objects.select_related(
        'bill', 'bill__customer'
    ).order_by('-payment_date')[:5]

    # Revenue trend data (last 6 months)
    today = timezone.now()
    six_months_ago = today - timedelta(days=180)
    monthly_revenue = (
        Payment.objects
        .filter(payment_date__gte=six_months_ago)
        .annotate(month=TruncMonth('payment_date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    revenue_labels = [entry['month'].strftime('%B %Y') for entry in monthly_revenue]
    revenue_data = [float(entry['total']) for entry in monthly_revenue]

    # Customer distribution by plan
    plan_distribution = (
        Customer.objects
        .filter(status='approved')
        .values('plan__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    plan_labels = [entry['plan__name'] for entry in plan_distribution]
    plan_data = [entry['count'] for entry in plan_distribution]

    # Payment method distribution
    payment_methods = (
        Payment.objects
        .values('payment_method')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    payment_method_labels = [entry['payment_method'].replace('_', ' ').title()
                             for entry in payment_methods]
    payment_method_data = [entry['count'] for entry in payment_methods]

    context = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'pending_applications': pending_applications,
        'total_revenue': total_revenue,
        'recent_applications': recent_applications,
        'recent_payments': recent_payments,
        # Chart data
        'revenue_labels': revenue_labels,
        'revenue_data': revenue_data,
        'plan_labels': plan_labels,
        'plan_data': plan_data,
        'payment_method_labels': payment_method_labels,
        'payment_method_data': payment_method_data,
    }
    return render(request, 'admin_dashboard.html', context)


# Customer Management Views
@login_required(login_url='admin_login')
def customer_list(request):
    customers = Customer.objects.select_related('user', 'plan').all()
    return render(request, 'customer_list.html', {'customers': customers})


@login_required(login_url='admin_login')
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    bills = Bill.objects.filter(customer=customer)
    payments = Payment.objects.filter(bill__customer=customer)
    return render(request, 'customer_detail.html', {
        'customer': customer,
        'bills': bills,
        'payments': payments
    })


@login_required(login_url='admin_login')
def customer_application(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            customer.status = 'approved'
            notification_type = 'application'
            message = 'Your application has been approved!'

            # Generate the first bill
            bill_date = timezone.now().date()
            due_date = bill_date + timedelta(days=30)  # Due in 30 days

            # Create the bill
            Bill.objects.create(
                customer=customer,
                amount=customer.plan.price,  # Use the plan's price
                bill_date=bill_date,
                due_date=due_date,
                status='unpaid'
            )

            # Add bill information to notification
            message += f'\nYour first bill of ₱{customer.plan.price} has been generated. Due date: {due_date.strftime("%B %d, %Y")}'

            # Update email message to be more professional
            email_message = f"""Dear {customer.user.get_full_name()},

We are pleased to inform you that your cable TV service application has been approved. Your service will be installed on {customer.installation_date} at {customer.installation_time}.

Your first bill of ₱{customer.plan.price} has been generated and is due on {due_date.strftime("%B %d, %Y")}.

Thank you for choosing our service.

Best regards,
Kabacan Northwest Cable TV Network Team"""

        elif action == 'reject':
            customer.status = 'rejected'
            notification_type = 'application'
            message = 'Your application has been rejected.'

            # Update email message
            email_message = f"""Dear {customer.user.get_full_name()},
                
We regret to inform you that we are unable to approve your cable TV service application at this time.

If you have any questions, please don't hesitate to contact us.

Best regards,
Kabacan Northwest Cable TV Network Team"""

        customer.save()

        # Create notification
        Notification.objects.create(
            customer=customer,
            type=notification_type,
            title='Application Status Update',
            message=message
        )

        # Send email
        send_mail(
            subject='Application Status Update',
            message=email_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[customer.user.email],
            fail_silently=True,
        )

        messages.success(request, f'Application {action}d successfully.')
        return redirect('customer_list')

    return render(request, 'customer_application.html', {'customer': customer})


@login_required(login_url='admin_login')
def customer_add(request):
    plans = CablePlan.objects.all()

    if request.method == 'POST':
        # Create User
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')

        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('customer_add')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return redirect('customer_add')

        try:
            # Create User instance
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Create Customer instance
            customer = Customer.objects.create(
                user=user,
                address=request.POST.get('address'),
                phone=request.POST.get('phone'),
                plan_id=request.POST.get('plan'),
                status='pending'
            )

            # Create welcome notification
            Notification.objects.create(
                customer=customer,
                type='application',
                title='Welcome to Kabacan Northwest Cable TV Network',
                message=f'Thank you for registering with us! Your application is under review.'
            )

            messages.success(request, 'Customer added successfully.')
            return redirect('customer_detail', customer_id=customer.id)

        except Exception as e:
            # If any error occurs, delete the user if created
            if 'user' in locals():
                user.delete()
            messages.error(request, f'Error creating customer: {str(e)}')
            return redirect('customer_add')

    return render(request, 'customer_add.html', {'plans': plans})


@login_required(login_url='admin_login')
def customer_edit(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    plans = CablePlan.objects.all()

    if request.method == 'POST':
        try:
            # Get the new email and username from the form
            new_email = request.POST.get('email')
            new_username = request.POST.get('username')

            # Check if email exists and belongs to a different user
            if (User.objects.filter(email=new_email)
                    .exclude(id=customer.user.id)
                    .exists()):
                messages.error(request, 'Email already exists for another user.')
                return redirect('customer_edit', customer_id=customer_id)

            # Check if username exists and belongs to a different user
            if (User.objects.filter(username=new_username)
                    .exclude(id=customer.user.id)
                    .exists()):
                messages.error(request, 'Username already exists for another user.')
                return redirect('customer_edit', customer_id=customer_id)

            # Update User information
            customer.user.username = new_username
            customer.user.first_name = request.POST.get('first_name')
            customer.user.last_name = request.POST.get('last_name')
            customer.user.email = new_email

            # Update password if provided
            new_password = request.POST.get('password')
            if new_password:
                customer.user.set_password(new_password)

            customer.user.save()

            # Update Customer information
            customer.address = request.POST.get('address')
            customer.phone = request.POST.get('phone')
            customer.plan_id = request.POST.get('plan')
            customer.status = request.POST.get('status')
            customer.installation_date = request.POST.get('installation_date')
            customer.installation_time = request.POST.get('installation_time')

            customer.save()

            messages.success(request, 'Customer updated successfully.')
            return redirect('customer_detail', customer_id=customer.id)

        except Exception as e:
            messages.error(request, f'Error updating customer: {str(e)}')
            return redirect('customer_edit', customer_id=customer_id)

    return render(request, 'customer_edit.html', {
        'customer': customer,
        'plans': plans
    })


@login_required(login_url='admin_login')
def customer_delete(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    # Check for unpaid bills
    bills_exist = Bill.objects.filter(customer=customer, status='unpaid').exists()

    if request.method == 'POST':
        try:
            # Check if customer has any pending bills
            if bills_exist:
                messages.error(request, 'Cannot delete customer with pending bills.')
                return redirect('customer_detail', customer_id=customer_id)

            with transaction.atomic():
                # Store user instance to delete after customer
                user = customer.user

                # Delete customer (this will cascade delete related records)
                customer.delete()

                # Delete user
                user.delete()

            messages.success(request, 'Customer deleted successfully.')
            return redirect('customer_list')

        except Exception as e:
            messages.error(request, f'Error deleting customer: {str(e)}')
            return redirect('customer_detail', customer_id=customer_id)

    return render(request, 'customer_delete.html', {
        'customer': customer,
        'bills_exist': bills_exist
    })


# Plan Management Views
@login_required(login_url='admin_login')
def plan_list(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            # Handle plan creation
            CablePlan.objects.create(
                name=request.POST.get('name'),
                description=request.POST.get('description'),
                price=request.POST.get('price'),
                channels=request.POST.get('channels'),
                features=request.POST.get('features')
            )
            messages.success(request, 'Plan created successfully.')

        elif action == 'edit':
            # Handle plan editing
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(CablePlan, id=plan_id)
            plan.name = request.POST.get('name')
            plan.description = request.POST.get('description')
            plan.price = request.POST.get('price')
            plan.channels = request.POST.get('channels')
            plan.features = request.POST.get('features')
            plan.save()
            messages.success(request, 'Plan updated successfully.')

        elif action == 'delete':
            # Handle plan deletion
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(CablePlan, id=plan_id)
            plan.delete()
            messages.success(request, 'Plan deleted successfully.')

        return redirect('plan_list')

    plans = CablePlan.objects.all()
    return render(request, 'plan_list.html', {'plans': plans})


# Billing Views
@login_required(login_url='admin_login')
def bill_list(request):
    # Modify the bills queryset to include customer and plan information
    bills = Bill.objects.select_related(
        'customer',
        'customer__user',
        'customer__plan'
    ).all()
    customers = Customer.objects.filter(status='approved').select_related('user')

    # Get filter parameters from URL
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Apply filters
    if status:
        bills = bills.filter(status=status)
    if start_date:
        bills = bills.filter(bill_date__gte=start_date)
    if end_date:
        bills = bills.filter(bill_date__lte=end_date)

    context = {
        'bills': bills,
        'customers': customers,
        'paid_bills_count': bills.filter(status='paid').count(),
        'unpaid_bills_count': bills.filter(status='unpaid').count(),
        'overdue_bills': bills.filter(status='overdue').count(),
        'current_filters': {
            'status': status,
            'start_date': start_date,
            'end_date': end_date,
        }
    }
    return render(request, 'bill_list.html', context)


@login_required(login_url='admin_login')
def generate_bill(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    # Get previous bills for this customer
    previous_bills = Bill.objects.filter(customer=customer).order_by('-bill_date')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        bill_date = request.POST.get('bill_date')
        due_date = request.POST.get('due_date')

        bill = Bill.objects.create(
            customer=customer,
            amount=amount,
            bill_date=bill_date,
            due_date=due_date,
            status='unpaid'
        )

        # Create notification
        Notification.objects.create(
            customer=customer,
            type='payment',
            title='New Bill Generated',
            message=f'A new bill of ₱{amount} has been generated. Due date: {due_date}'
        )

        # After bill creation, send email
        email_message = f"""Dear {customer.user.get_full_name()},

Your cable TV service bill for {bill_date} has been generated.

Amount Due: ₱{amount}
Due Date: {due_date}

Please ensure timely payment to avoid service interruption.

Best regards,
Kabacan Northwest Cable TV Network Team"""

        send_mail(
            subject='New Bill Generated',
            message=email_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[customer.user.email],
            fail_silently=True,
        )

        messages.success(request, 'Bill generated successfully.')
        return redirect('bill_list')

    context = {
        'customer': customer,
        'previous_bills': previous_bills,
    }
    return render(request, 'generate_bill.html', context)


@login_required(login_url='admin_login')
def edit_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)

    if request.method == 'POST':
        try:
            bill.customer_id = request.POST.get('customer_id')
            bill.amount = request.POST.get('amount')
            bill.bill_date = request.POST.get('bill_date')
            bill.due_date = request.POST.get('due_date')
            bill.status = request.POST.get('status')
            bill.save()

            messages.success(request, 'Bill updated successfully.')
            return redirect('bill_list')
        except Exception as e:
            messages.error(request, f'Error updating bill: {str(e)}')
            return redirect('bill_list')

    return redirect('bill_list')


@login_required(login_url='admin_login')
def delete_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)

    if request.method == 'POST':
        try:
            bill.delete()
            messages.success(request, 'Bill deleted successfully.')
            return redirect('bill_list')
        except Exception as e:
            messages.error(request, f'Error deleting bill: {str(e)}')

    return redirect('bill_list')


# Payment Views
@login_required(login_url='admin_login')
def payment_list(request):
    # Get all payments with related data
    payments = Payment.objects.select_related('bill', 'bill__customer').all()

    # Calculate statistics
    total_payments = payments.count()
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
    todays_payments = payments.filter(payment_date__date=timezone.now().date()).count()
    average_payment = total_revenue / total_payments if total_payments > 0 else 0

    # Get payment history data for chart (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    payment_history = (
        Payment.objects
        .filter(payment_date__gte=thirty_days_ago)
        .values('payment_date__date')
        .annotate(daily_total=Sum('amount'))
        .order_by('payment_date__date')
    )

    payment_dates = [p['payment_date__date'].strftime('%Y-%m-%d') for p in payment_history]
    payment_amounts = [float(p['daily_total']) for p in payment_history]

    # Get payment methods distribution
    payment_methods = (
        Payment.objects
        .values('payment_method')
        .annotate(count=Count('id'))
        .order_by('payment_method')
    )

    payment_methods_data = [p['count'] for p in payment_methods]

    context = {
        'payments': payments,
        'total_payments': total_payments,
        'total_revenue': total_revenue,
        'todays_payments': todays_payments,
        'average_payment': average_payment,
        'payment_dates': payment_dates,
        'payment_amounts': payment_amounts,
        'payment_methods_data': payment_methods_data,
    }

    return render(request, 'payment_list.html', context)


@login_required(login_url='admin_login')
def record_payment(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)

    # Get previous payments for this customer
    previous_payments = Payment.objects.filter(
        bill__customer=bill.customer
    ).select_related('bill')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        transaction_id = request.POST.get('transaction_id')

        Payment.objects.create(
            bill=bill,
            amount=amount,
            payment_method=payment_method,
            transaction_id=transaction_id
        )

        bill.status = 'paid'
        bill.payment_date = timezone.now()
        bill.save()

        # Create notification
        Notification.objects.create(
            customer=bill.customer,
            type='payment',
            title='Payment Received',
            message=f'Payment of ₱{amount} received for bill dated {bill.bill_date.strftime("%Y-%m-%d")}'
        )

        # After payment recording, send confirmation email
        email_message = f"""Dear {bill.customer.user.get_full_name()},
                        
We have received your payment of ₱{amount} for your cable TV service bill dated {bill.bill_date.strftime("%B %d, %Y")}.

Thank you for your payment.

Best regards,
Kabacan Northwest Cable TV Network Team"""

        send_mail(
            subject='Payment Confirmation',
            message=email_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[bill.customer.user.email],
            fail_silently=True,
        )

        messages.success(request, 'Payment recorded successfully.')
        return redirect('payment_list')

    return render(request, 'record_payment.html', {
        'bill': bill,
        'previous_payments': previous_payments  # Add this to the context
    })


# Report Views
@login_required(login_url='admin_login')
def report_dashboard(request):
    today = timezone.now().date()
    current_year = today.year
    current_month = today.month

    # Get all approved customers with their latest bills and payments
    customers = Customer.objects.select_related('user', 'plan').prefetch_related(
        'bill_set', 'bill_set__payment_set'
    ).filter(status='approved')

    # Calculate paid subscribers (customers with paid bills in current month)
    paid_subscribers_list = []
    for customer in customers:
        latest_paid_bill = customer.bill_set.filter(
            status='paid',
            bill_date__year=current_year,
            bill_date__month=current_month
        ).first()
        if latest_paid_bill:
            latest_payment = latest_paid_bill.payment_set.first()
            paid_subscribers_list.append({
                'user': customer.user,
                'plan': customer.plan,
                'last_payment_date': latest_payment.payment_date if latest_payment else None,
                'last_payment_amount': latest_payment.amount if latest_payment else 0
            })

    # Calculate unpaid subscribers
    unpaid_subscribers_list = []
    for customer in customers:
        unpaid_bill = customer.bill_set.filter(status='unpaid').first()
        if unpaid_bill:
            days_overdue = (today - unpaid_bill.due_date).days if today > unpaid_bill.due_date else 0
            unpaid_subscribers_list.append({
                'user': customer.user,
                'plan': customer.plan,
                'bill': unpaid_bill,
                'days_overdue': days_overdue
            })

    # Calculate monthly revenue data (for the current year)
    monthly_revenue_data = []
    monthly_revenue_labels = []

    for month in range(1, 13):
        month_revenue = Payment.objects.filter(
            payment_date__year=current_year,
            payment_date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_revenue_data.append(float(month_revenue))
        monthly_revenue_labels.append(timezone.datetime(current_year, month, 1).strftime('%B'))

    # Calculate current month's revenue
    current_month_revenue = Payment.objects.filter(
        payment_date__year=current_year,
        payment_date__month=current_month
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        # Statistics
        'paid_subscribers': len(paid_subscribers_list),
        'unpaid_subscribers': len(unpaid_subscribers_list),
        'monthly_revenue': {'total': current_month_revenue},

        # Detailed lists for tables
        'paid_subscribers_list': paid_subscribers_list,
        'unpaid_subscribers_list': unpaid_subscribers_list,

        # Chart data
        'monthly_revenue_labels': monthly_revenue_labels,
        'monthly_revenue_data': monthly_revenue_data,
    }

    return render(request, 'report_dashboard.html', context)


# Notification Views
@login_required(login_url='admin_login')
def notification_list(request):
    notifications = Notification.objects.select_related('customer').all()
    return render(request, 'notification_list.html', {'notifications': notifications})


@login_required(login_url='admin_login')
def send_notification(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    if request.method == 'POST':
        notification_type = request.POST.get('type')
        title = request.POST.get('title')
        message = request.POST.get('message')

        Notification.objects.create(
            customer=customer,
            type=notification_type,
            title=title,
            message=message
        )

        # Send email
        send_mail(
            title,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [customer.user.email],
            fail_silently=True,
        )

        messages.success(request, 'Notification sent successfully.')
        return redirect('notification_list')

    return render(request, 'send_notification.html', {'customer': customer})
