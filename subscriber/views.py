import re
from datetime import datetime, date
from decimal import Decimal
from io import BytesIO

import requests
import stripe
from PIL import Image
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from management.models import (
    CablePlan, Customer, Bill, Payment, Notification
)

stripe.api_key = settings.STRIPE_SECRET_KEY


def login_view(request):
    if request.user.is_authenticated:
        return redirect('subscriber:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if not remember:
                request.session.set_expiry(0)

            messages.success(request, 'Welcome back! You have successfully logged in.')
            return redirect('subscriber:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'subscriber/login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('subscriber:dashboard')

    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        address = request.POST.get('address')

        # Validate data
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username is already taken.')
            return render(request, 'subscriber/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email is already registered.')
            return render(request, 'subscriber/register.html')

        # Validate password match
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'subscriber/register.html')

        # Validate password strength
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'subscriber/register.html')

        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Create customer profile
            customer = Customer.objects.create(
                user=user,
                phone=phone,
                address=address
            )

            # Send email to management about new registration
            email_message = f"""[New Account] {first_name} {last_name}

CUSTOMER DETAILS
Name: {first_name} {last_name}
Contact: {phone}
Email: {email}
Address: {address}

Action Required: Verify customer information

--
Kabacan Northwest Cable TV Network"""

            send_mail(
                subject=f'New Customer Registration - {first_name} {last_name}',
                message=email_message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[settings.DEFAULT_FROM_EMAIL],
                fail_silently=True,
            )

            messages.success(request, 'Account created successfully! Welcome to Cable TV Network.')
            return redirect('subscriber:login')

        except Exception as e:
            messages.error(request, 'An error occurred while creating your account. Please try again.')

    return render(request, 'subscriber/register.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('subscriber:login')


@login_required(login_url='subscriber:login')
def dashboard(request):
    try:
        customer = Customer.objects.get(user=request.user)
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found.")
        return redirect('login')

    context = {
        'customer': customer,
        'current_plan': customer.plan,
        'recent_bills': Bill.objects.filter(customer=customer).order_by('-bill_date')[:5],
        'recent_payments': Payment.objects.filter(bill__customer=customer).order_by('-payment_date')[:5],
        'notifications': Notification.objects.filter(customer=customer, is_read=False)[:5],
        'total_due': Bill.objects.filter(customer=customer, status='unpaid').aggregate(
            total=models.Sum('amount'))['total'] or 0,
    }
    return render(request, 'subscriber/dashboard.html', context)


@login_required(login_url='subscriber:login')
def plan_list(request):
    plans = CablePlan.objects.all().order_by('price')
    try:
        customer = Customer.objects.get(user=request.user)
        current_plan = customer.plan
    except Customer.DoesNotExist:
        current_plan = None

    # Process features for each plan
    for plan in plans:
        plan.feature_list = plan.features.split('\n') if plan.features else []

    context = {
        'plans': plans,
        'current_plan': current_plan
    }
    return render(request, 'subscriber/plan_list.html', context)


@login_required(login_url='subscriber:login')
def plan_detail(request, plan_id):
    plan = get_object_or_404(CablePlan, id=plan_id)
    return render(request, 'subscriber/plan_detail.html', {'plan': plan})


@login_required(login_url='subscriber:login')
def plan_apply(request, plan_id):
    plan = get_object_or_404(CablePlan, id=plan_id)
    customer = get_object_or_404(Customer, user=request.user)

    # Process features for current plan
    plan.feature_list = plan.features.split('\n') if plan.features else []

    if request.method == 'POST':
        # Get form data
        installation_address = request.POST.get('installation_address')
        installation_date = request.POST.get('installation_date')
        installation_time = request.POST.get('installation_time')
        installation_notes = request.POST.get('installation_notes')

        # Update customer info
        customer.plan = plan
        customer.status = 'pending'
        customer.address = installation_address
        customer.installation_date = installation_date
        customer.installation_time = installation_time
        customer.installation_notes = installation_notes
        customer.save()

        # Send email to management
        email_message = f"""[Plan Application] {customer.user.get_full_name()}

CUSTOMER
Full Name: {customer.user.get_full_name()}
Contact: {customer.phone}
Email: {customer.user.email}

PLAN REQUEST
Service: {plan.name}
Monthly Fee: ₱{plan.price}

INSTALLATION
Schedule: {installation_date} at {installation_time}
Location: {installation_address}
Notes: {installation_notes}

--
Kabacan Northwest Cable TV Network"""

        send_mail(
            subject=f'New Plan Application - {customer.user.get_full_name()}',
            message=email_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[settings.DEFAULT_FROM_EMAIL],  # Send to management email
            fail_silently=True,
        )

        messages.success(request, 'Your plan application has been submitted successfully.')
        return redirect('subscriber:my_plan')

    # Add min installation date (tomorrow)
    context = {
        'plan': plan,
        'customer': customer,
        'min_installation_date': timezone.now().date() + timezone.timedelta(days=1)
    }
    return render(request, 'subscriber/plan_apply.html', context)


@login_required(login_url='subscriber:login')
def my_plan(request):
    customer = get_object_or_404(Customer, user=request.user)

    # Process features for current plan
    if customer.plan:
        customer.plan.feature_list = customer.plan.features.split('\n') if customer.plan.features else []

    # Get latest bill to determine next bill date
    latest_bill = Bill.objects.filter(customer=customer).order_by('-bill_date').first()
    if latest_bill:
        next_bill_date = latest_bill.bill_date + timezone.timedelta(days=30)
    else:
        next_bill_date = timezone.now().date() + timezone.timedelta(days=30)

    # Calculate outstanding balance
    outstanding_balance = Bill.objects.filter(
        customer=customer,
        status='unpaid'
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'customer': customer,
        'next_bill_date': next_bill_date,
        'outstanding_balance': outstanding_balance
    }

    return render(request, 'subscriber/my_plan.html', context)


@login_required(login_url='subscriber:login')
def billing_list(request):
    customer = get_object_or_404(Customer, user=request.user)
    bills = Bill.objects.filter(customer=customer).order_by('-bill_date')

    # Calculate statistics
    total_bills = bills.count()
    paid_bills = bills.filter(status='paid').count()
    unpaid_bills = bills.filter(status='unpaid').count()
    overdue_bills = bills.filter(status='overdue').count()

    # Calculate total amounts
    total_due = bills.filter(status='unpaid').aggregate(
        total=models.Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'bills': bills,
        'total_bills': total_bills,
        'paid_bills': paid_bills,
        'unpaid_bills': unpaid_bills,
        'overdue_bills': overdue_bills,
        'total_due': total_due,
    }
    return render(request, 'subscriber/billing_list.html', context)


@login_required(login_url='subscriber:login')
def billing_detail(request, bill_id):
    customer = get_object_or_404(Customer, user=request.user)
    bill = get_object_or_404(Bill, id=bill_id, customer=customer)
    return render(request, 'subscriber/billing_detail.html', {'bill': bill})


@login_required(login_url='subscriber:login')
def payment_list(request):
    customer = get_object_or_404(Customer, user=request.user)
    payments = Payment.objects.filter(bill__customer=customer).order_by('-payment_date')

    # Calculate payment statistics
    total_payments = payments.count()
    total_amount_paid = payments.aggregate(
        total=models.Sum('amount'))['total'] or Decimal('0.00')

    # Get last payment
    last_payment = payments.first()

    # Calculate outstanding balance
    outstanding_balance = Bill.objects.filter(
        customer=customer,
        status='unpaid'
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'payments': payments,
        'total_payments': total_payments,
        'total_amount_paid': total_amount_paid,
        'last_payment': last_payment,
        'outstanding_balance': outstanding_balance
    }
    return render(request, 'subscriber/payment_list.html', context)


@login_required(login_url='subscriber:login')
def payment_detail(request, payment_id):
    customer = get_object_or_404(Customer, user=request.user)
    payment = get_object_or_404(Payment, id=payment_id, bill__customer=customer)
    return render(request, 'subscriber/payment_detail.html', {'payment': payment})


@login_required(login_url='subscriber:login')
def make_payment(request, bill_id):
    customer = get_object_or_404(Customer, user=request.user)
    bill = get_object_or_404(Bill, id=bill_id, customer=customer)

    if request.method == 'POST':
        # Check if the request is JSON (for Stripe)
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
            payment_method = data.get('payment_method')
        else:
            payment_method = request.POST.get('payment_method')

        if payment_method == 'stripe':
            try:
                # Create Stripe Checkout Session
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'php',
                            'unit_amount': int(bill.amount * 100),  # Convert to cents
                            'product_data': {
                                'name': f'Bill Payment #{bill.id}',
                                'description': f'Payment for Cable TV Bill #{bill.id}',
                            },
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=request.build_absolute_uri(
                        reverse('subscriber:payment_success')
                    ) + f'?session_id={{CHECKOUT_SESSION_ID}}&bill_id={bill.id}',
                    cancel_url=request.build_absolute_uri(
                        reverse('subscriber:payment_cancel')
                    ),
                    metadata={
                        'bill_id': bill.id,
                        'customer_id': customer.id,
                    }
                )

                # Create a pending payment record
                Payment.objects.create(
                    bill=bill,
                    amount=bill.amount,
                    payment_method='stripe',
                    transaction_id=checkout_session.id
                )

                return JsonResponse({
                    'session_id': checkout_session.id
                })

            except Exception as e:
                return JsonResponse({
                    'error': str(e)
                }, status=400)

        # GCash payment
        elif payment_method == 'gcash':
            if 'receipt' not in request.FILES:
                messages.error(request, 'Please upload your GCash receipt')
                return redirect('subscriber:make_payment', bill_id=bill_id)

            # Get the confirmed values from the form
            confirmed_amount = request.POST.get('confirmed_amount')
            confirmed_reference = request.POST.get('confirmed_reference')
            confirmed_date = request.POST.get('confirmed_date')

    context = {
        'bill': bill,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    }
    return render(request, 'subscriber/make_payment.html', context)


def compress_image(image_file):
    """Compress image to reduce size"""
    img = Image.open(image_file)
    # Convert to RGB if image is in RGBA mode
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    output = BytesIO()
    # Save with reduced quality
    img.save(output, format='JPEG', quality=85, optimize=True)
    output.seek(0)
    return output


@login_required(login_url='subscriber:login')
def process_receipt(request, bill_id):
    """Handle receipt processing via OCR.space API"""
    if request.method == 'POST' and request.FILES.get('receipt'):
        try:
            receipt = request.FILES['receipt']

            # Process the receipt using OCR.space API
            url = "https://api.ocr.space/parse/image"
            api_key = settings.OCR_SPACE_API_KEY

            # Compress image
            compressed_image = compress_image(receipt)

            files = {
                'file': ('receipt.jpg', compressed_image, 'image/jpeg')
            }

            payload = {
                'apikey': api_key,
                'language': 'eng',
                'isOverlayRequired': False,
                'detectOrientation': True,
                'scale': True,
                'OCREngine': 2,
                'filetype': 'jpg'
            }

            response = requests.post(url, files=files, data=payload)
            result = response.json()

            if result.get('ParsedResults'):
                text = result['ParsedResults'][0]['ParsedText']
                lines = text.split('\n')

                # Extract information
                ref_pattern = r'\d{4}\s*\d{3}\s*\d{6}'
                amount_pattern = r'[₱₽]\s*([\d,]+\.?\d*)'
                date_pattern = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}'

                ref_number = None
                total_amount = None
                receipt_date = None

                # Find Reference Number
                for line in lines:
                    if 'ref' in line.lower() or 'reference' in line.lower():
                        ref_match = re.search(ref_pattern, line)
                        if ref_match:
                            ref_number = ref_match.group(0).replace(' ', '')
                            break

                # Find Total Amount
                for line in lines:
                    amount_match = re.search(amount_pattern, line)
                    if amount_match:
                        amount_str = amount_match.group(1)
                        try:
                            total_amount = float(amount_str.replace(',', ''))
                            break
                        except ValueError:
                            continue

                # Find Date
                for line in lines:
                    date_match = re.search(date_pattern, line)
                    if date_match:
                        receipt_date = date_match.group(0)
                        break

                return JsonResponse({
                    'success': True,
                    'data': {
                        'reference_number': ref_number,
                        'total_amount': total_amount,
                        'receipt_date': receipt_date
                    }
                })

            return JsonResponse({
                'success': False,
                'error': 'Could not extract information from receipt'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({
        'success': False,
        'error': 'Invalid request'
    })


@require_POST
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )

        if event.type == 'checkout.session.completed':
            session = event.data.object
            
            # Get the payment record
            payment = Payment.objects.get(transaction_id=session.id)
            
            # Update bill status
            bill = payment.bill
            bill.status = 'paid'
            bill.payment_date = timezone.now()
            bill.save()
            
            # Create notification
            Notification.objects.create(
                customer=bill.customer,
                type='payment',
                title='Payment Successful',
                message=f'Your payment of ₱{payment.amount} for Bill #{bill.id} has been received.'
            )

        return HttpResponse(status=200)

    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)
    except Exception as e:
        return HttpResponse(status=400)


@login_required(login_url='subscriber:login')
def profile_view(request):
    customer = get_object_or_404(Customer, user=request.user)

    # Get recent bills
    recent_bills = Bill.objects.filter(customer=customer).order_by('-bill_date')[:5]

    # Get recent payments
    recent_payments = Payment.objects.filter(bill__customer=customer).order_by('-payment_date')[:5]

    # Get recent notifications
    recent_notifications = Notification.objects.filter(customer=customer).order_by('-sent_date')[:5]

    # Combine all activities
    activities = []

    # Add bills to activities
    for bill in recent_bills:
        # Convert date to datetime if it's a date object
        bill_date = timezone.make_aware(datetime.combine(bill.bill_date, datetime.min.time())) if isinstance(
            bill.bill_date, date) else bill.bill_date
        activities.append({
            'date': bill_date,
            'title': 'New Bill Generated',
            'description': f'Bill amount: ₱{bill.amount} due on {bill.due_date.strftime("%B %d, %Y")}'
        })

    # Add payments to activities
    for payment in recent_payments:
        activities.append({
            'date': payment.payment_date,
            'title': 'Payment Made',
            'description': f'Paid ₱{payment.amount} via {payment.get_payment_method_display()}'
        })

    # Add notifications to activities
    for notification in recent_notifications:
        activities.append({
            'date': notification.sent_date,
            'title': notification.title,
            'description': notification.message
        })

    # Sort activities by date, most recent first
    activities.sort(key=lambda x: x['date'], reverse=True)

    # Take only the 10 most recent activities
    recent_activities = activities[:10]

    context = {
        'customer': customer,
        'recent_activities': recent_activities
    }

    return render(request, 'subscriber/profile_view.html', context)


@login_required(login_url='subscriber:login')
def profile_edit(request):
    customer = get_object_or_404(Customer, user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            # Get the new email
            new_email = request.POST.get('email')

            # Check if email exists and belongs to a different user
            if (User.objects.filter(email=new_email)
                    .exclude(id=request.user.id)
                    .exists()):
                messages.error(request, 'Email already exists for another user.')
                return redirect('subscriber:profile_edit')

            # Update user info
            request.user.first_name = request.POST.get('first_name')
            request.user.last_name = request.POST.get('last_name')
            request.user.email = new_email
            request.user.save()

            # Update customer info
            customer.phone = request.POST.get('phone')
            customer.address = request.POST.get('address')
            customer.save()

            messages.success(request, 'Profile updated successfully.')
            return redirect('subscriber:profile')

        elif action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            # Verify current password
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return redirect('subscriber:profile_edit')

            # Check if new passwords match
            if new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
                return redirect('subscriber:profile_edit')

            # Check password strength (you can add more validation)
            if len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
                return redirect('subscriber:profile_edit')

            # Change password
            request.user.set_password(new_password)
            request.user.save()

            # Update session to prevent logout
            update_session_auth_hash(request, request.user)

            messages.success(request, 'Password changed successfully.')
            return redirect('subscriber:profile')

    return render(request, 'subscriber/profile_edit.html', {'customer': customer})


@login_required(login_url='subscriber:login')
def notification_list(request):
    customer = get_object_or_404(Customer, user=request.user)
    notifications = Notification.objects.filter(customer=customer).order_by('-sent_date')
    return render(request, 'subscriber/notification_list.html', {'notifications': notifications})


@login_required(login_url='subscriber:login')
def notification_detail(request, notification_id):
    customer = get_object_or_404(Customer, user=request.user)
    notification = get_object_or_404(Notification, id=notification_id, customer=customer)

    if not notification.is_read:
        notification.is_read = True
        notification.save()

    return render(request, 'subscriber/notification_detail.html', {'notification': notification})


@login_required(login_url='subscriber:login')
def mark_notifications_read(request):
    customer = get_object_or_404(Customer, user=request.user)
    Notification.objects.filter(customer=customer, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read')
    return JsonResponse({'status': 'success'})


@login_required(login_url='subscriber:login')
def mark_notification_read(request, notification_id):
    customer = get_object_or_404(Customer, user=request.user)
    notification = get_object_or_404(Notification, id=notification_id, customer=customer)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'success'})


@login_required(login_url='subscriber:login')
def payment_success(request):
    session_id = request.GET.get('session_id')
    bill_id = request.GET.get('bill_id')
    
    try:
        # Verify the payment session
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            # Update the payment record
            payment = Payment.objects.get(transaction_id=session_id)
            payment.save()
            
            # Update the bill status
            bill = Bill.objects.get(id=bill_id)
            bill.status = 'paid'
            bill.payment_date = timezone.now()
            bill.save()
            
            messages.success(request, 'Payment successful! Thank you for your payment.')
            return redirect('subscriber:payment_detail', payment_id=payment.id)
            
    except Exception as e:
        messages.error(request, f'Error processing payment: {str(e)}')
    
    return redirect('subscriber:billing_list')


@login_required(login_url='subscriber:login')
def payment_cancel(request):
    messages.warning(request, 'Payment was cancelled.')
    return redirect('subscriber:billing_list')
