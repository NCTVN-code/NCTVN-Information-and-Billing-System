from django.apps import AppConfig
from django.utils import timezone


class ManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'management'

    def ready(self):
        try:
            from django_q.models import Schedule
            # Delete existing schedule
            Schedule.objects.filter(name='check_bills_daily').delete()

            # Create new schedule to run at midnight daily
            Schedule.objects.create(
                name='check_bills_daily',
                func='management.tasks.check_bills',
                schedule_type=Schedule.DAILY,
                next_run=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
                repeats=-1
            )
        except Exception as e:
            print(f"Failed to initialize schedule: {e}")
