# Generated by Django 3.2.15 on 2022-09-13 20:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0005_sapsuccessfactorsenterprisecustomerconfiguration_dry_run_mode_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='friendly_status_message',
            field=models.CharField(blank=True, default=None, help_text='A user-friendly API response status message.', max_length=255, null=True),
        ),
    ]
