# Generated by Django 4.2.13 on 2024-05-29 07:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0032_delete_historicaldegreedenterprisecustomerconfiguration'),
    ]

    operations = [
        migrations.AddField(
            model_name='degreedlearnerdatatransmissionaudit',
            name='is_transmitted',
            field=models.BooleanField(default=False),
        ),
    ]
