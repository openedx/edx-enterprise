# Generated by Django 3.2.16 on 2022-12-09 08:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0165_alter_enterprisecustomerreportingconfiguration_pgp_encryption_key'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalenterpriseanalyticsuser',
            name='enterprise_customer_user',
        ),
        migrations.RemoveField(
            model_name='historicalenterpriseanalyticsuser',
            name='history_user',
        ),
        migrations.DeleteModel(
            name='EnterpriseAnalyticsUser',
        ),
        migrations.DeleteModel(
            name='HistoricalEnterpriseAnalyticsUser',
        ),
    ]
