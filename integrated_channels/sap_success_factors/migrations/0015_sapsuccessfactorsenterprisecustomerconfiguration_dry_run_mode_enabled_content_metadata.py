# Generated by Django 3.2.21 on 2023-09-21 12:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0014_alter_sapsuccessfactorsenterprisecustomerconfiguration_show_course_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='dry_run_mode_enabled_content_metadata',
            field=models.BooleanField(default=False, help_text='Enables dry run mode for content metadata transmission.'),
        ),
    ]
