from django.urls import path
from . import views

app_name = 'subscriber'

urlpatterns = [
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Plans
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/<int:plan_id>/', views.plan_detail, name='plan_detail'),
    path('plans/apply/<int:plan_id>/', views.plan_apply, name='plan_apply'),
    path('my-plan/', views.my_plan, name='my_plan'),
    
    # Billing
    path('billing/', views.billing_list, name='billing_list'),
    path('billing/<int:bill_id>/', views.billing_detail, name='billing_detail'),
    
    # Payments
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/<int:payment_id>/', views.payment_detail, name='payment_detail'),
    path('make-payment/<int:bill_id>/', views.make_payment, name='make_payment'),
    path('process-receipt/<int:bill_id>/', views.process_receipt, name='process_receipt'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/cancel/', views.payment_cancel, name='payment_cancel'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    
    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:notification_id>/', views.notification_detail, name='notification_detail'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('notifications/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

]
