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

            # Create new schedule
            Schedule.objects.create(
                name='check_bills_daily',
                func='management.tasks.check_bills',
                schedule_type=Schedule.MINUTES,
                minutes=1,
                next_run=timezone.now(),
                repeats=-1
            )
        except Exception as e:
            print(f"Failed to initialize schedule: {e}")
