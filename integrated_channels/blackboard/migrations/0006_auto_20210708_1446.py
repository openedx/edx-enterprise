# Generated by Django 2.2.20 on 2021-07-08 14:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blackboard', '0005_blackboardlearnerassessmentdatatransmissionaudit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='catalogs_to_transmit',
            field=models.TextField(blank=True, help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.', null=True),
        ),
        migrations.AlterField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='catalogs_to_transmit',
            field=models.TextField(blank=True, help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.', null=True),
        ),
    ]
