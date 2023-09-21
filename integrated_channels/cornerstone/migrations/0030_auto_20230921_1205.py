# Generated by Django 3.2.21 on 2023-09-21 12:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cornerstone', '0029_alter_historicalcornerstoneenterprisecustomerconfiguration_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='cornerstoneenterprisecustomerconfiguration',
            name='dry_run_mode_enabled_content_metadata',
            field=models.BooleanField(default=False, help_text='Enables dry run mode for content metadata transmission.'),
        ),
        migrations.AddField(
            model_name='historicalcornerstoneenterprisecustomerconfiguration',
            name='dry_run_mode_enabled_content_metadata',
            field=models.BooleanField(default=False, help_text='Enables dry run mode for content metadata transmission.'),
        ),
    ]
