# Generated by Django 3.2.21 on 2023-10-10 16:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cornerstone', '0029_alter_historicalcornerstoneenterprisecustomerconfiguration_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='cornerstoneenterprisecustomerconfiguration',
            name='disable_subject_metadata_transmission',
            field=models.BooleanField(default=False, help_text='If checked, subjects will not be sent to Cornerstone', verbose_name='Disable Subject Content Metadata Transmission'),
        ),
        migrations.AddField(
            model_name='historicalcornerstoneenterprisecustomerconfiguration',
            name='disable_subject_metadata_transmission',
            field=models.BooleanField(default=False, help_text='If checked, subjects will not be sent to Cornerstone', verbose_name='Disable Subject Content Metadata Transmission'),
        ),
    ]
