# Generated by Django 3.2.19 on 2024-02-20 07:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0031_alter_historicaldegreedenterprisecustomerconfiguration_options'),
    ]

    operations = [
        migrations.DeleteModel(
            name='HistoricalDegreedEnterpriseCustomerConfiguration',
        ),
    ]
