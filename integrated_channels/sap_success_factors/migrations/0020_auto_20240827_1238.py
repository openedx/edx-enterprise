# Generated by Django 3.2.23 on 2024-08-27 12:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0019_auto_20240827_0807'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='key',
        ),
        migrations.RemoveField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='secret',
        ),
    ]
