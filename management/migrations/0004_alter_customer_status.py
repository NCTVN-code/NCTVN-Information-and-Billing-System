# Generated by Django 4.2.17 on 2024-12-14 02:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0003_remove_customer_connection_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('disconnected', 'Disconnected')], default='pending', max_length=20),
        ),
    ]
