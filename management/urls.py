from django.urls import path
from .views import *

urlpatterns = [
    # Authentication
    path('login/', login_view, name='admin_login'),
    path('logout/', logout_view, name='admin_logout'),
    
    # Profile
    path('profile/', view_profile, name='view_admin_profile'),
    path('profile/edit/', edit_profile, name='edit_admin_profile'),
    
    # Dashboard
    path('', admin_dashboard, name='admin_dashboard'),
    
    # Customer Management
    path('customers/', customer_list, name='customer_list'),
    path('customers/add/', customer_add, name='customer_add'),
    path('customers/<int:customer_id>/', customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/edit/', customer_edit, name='customer_edit'),
    path('customers/<int:customer_id>/delete/', customer_delete, name='customer_delete'),
    path('customers/<int:customer_id>/application/', customer_application, name='customer_application'),
    
    # Plan Management
    path('plans/', plan_list, name='plan_list'),
    
    # Billing Management
    path('bills/', bill_list, name='bill_list'),
    path('bills/generate/<int:customer_id>/', generate_bill, name='generate_bill'),
    path('bills/<int:bill_id>/edit/', edit_bill, name='edit_bill'),
    path('bills/<int:bill_id>/delete/', delete_bill, name='delete_bill'),
    
    # Payment Management
    path('payments/', payment_list, name='payment_list'),
    path('payments/record/<int:bill_id>/', record_payment, name='record_payment'),
    
    # Reports
    path('reports/', report_dashboard, name='report_dashboard'),
]
