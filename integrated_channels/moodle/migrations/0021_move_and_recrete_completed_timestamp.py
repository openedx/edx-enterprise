# Generated by Django 3.2.15 on 2022-10-31 18:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moodle', '0020_auto_20221031_1855'),
    ]

    operations = [
        migrations.RenameField(
            model_name='moodlelearnerdatatransmissionaudit',
            old_name='completed_timestamp',
            new_name='moodle_completed_timestamp',
        ),
        migrations.AddField(
            model_name='moodlelearnerdatatransmissionaudit',
            name='completed_timestamp',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
