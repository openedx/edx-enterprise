# Generated by Django 3.2.12 on 2022-03-23 17:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0002_alter_sapsuccessfactorsenterprisecustomerconfiguration_display_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='completed_timestamp',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
