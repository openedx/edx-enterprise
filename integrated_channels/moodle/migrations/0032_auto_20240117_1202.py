# Generated by Django 3.2.23 on 2024-01-17 12:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('moodle', '0031_moodlelearnerdatatransmissionaudit_transmission_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalmoodleenterprisecustomerconfiguration',
            name='password',
        ),
        migrations.RemoveField(
            model_name='historicalmoodleenterprisecustomerconfiguration',
            name='token',
        ),
        migrations.RemoveField(
            model_name='historicalmoodleenterprisecustomerconfiguration',
            name='username',
        ),
        migrations.RemoveField(
            model_name='moodleenterprisecustomerconfiguration',
            name='password',
        ),
        migrations.RemoveField(
            model_name='moodleenterprisecustomerconfiguration',
            name='token',
        ),
        migrations.RemoveField(
            model_name='moodleenterprisecustomerconfiguration',
            name='username',
        ),
    ]
