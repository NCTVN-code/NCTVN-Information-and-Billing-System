from management.models import Notification

def notification_processor(request):
    if request.user.is_authenticated:
        try:
            # Get unread notifications count
            unread_count = Notification.objects.filter(
                customer__user=request.user,
                is_read=False
            ).count()
            
            # Get recent notifications
            recent_notifications = Notification.objects.filter(
                customer__user=request.user
            ).order_by('-sent_date')[:5]
            
            return {
                'unread_notifications_count': unread_count,
                'recent_notifications': recent_notifications
            }
        except:
            return {
                'unread_notifications_count': 0,
                'recent_notifications': []
            }
    return {
        'unread_notifications_count': 0,
        'recent_notifications': []
    } 