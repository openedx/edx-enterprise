# Generated by Django 3.2.23 on 2024-01-10 13:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moodle', '0032_auto_20231208_2345'),
    ]

    operations = [
        migrations.AddField(
            model_name='moodlelearnerdatatransmissionaudit',
            name='transmission_status',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]
