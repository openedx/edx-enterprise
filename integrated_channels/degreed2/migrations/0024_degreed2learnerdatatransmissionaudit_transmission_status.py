# Generated by Django 3.2.23 on 2024-01-10 13:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed2', '0023_alter_historicaldegreed2enterprisecustomerconfiguration_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='degreed2learnerdatatransmissionaudit',
            name='transmission_status',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]
