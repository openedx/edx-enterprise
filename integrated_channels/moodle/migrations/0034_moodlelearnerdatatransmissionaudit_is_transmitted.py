# Generated by Django 4.2.13 on 2024-05-29 07:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moodle', '0033_delete_historicalmoodleenterprisecustomerconfiguration'),
    ]

    operations = [
        migrations.AddField(
            model_name='moodlelearnerdatatransmissionaudit',
            name='is_transmitted',
            field=models.BooleanField(default=False),
        ),
    ]
