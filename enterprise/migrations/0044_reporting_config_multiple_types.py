# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0043_auto_20180507_0138'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomerreportingconfiguration',
            name='enterprise_customer',
            field=models.ForeignKey(related_name='reporting_configurations', verbose_name='Enterprise Customer', to='enterprise.EnterpriseCustomer'),
        ),
        migrations.AddField(
            model_name='enterprisecustomerreportingconfiguration',
            name='data_type',
            field=models.CharField(default='progress', help_text='The type of data this report should contain.', max_length=20, verbose_name='Data Type', choices=[('progress', 'progress'), ('catalog', 'catalog')]),
        ),
        migrations.AddField(
            model_name='enterprisecustomerreportingconfiguration',
            name='report_type',
            field=models.CharField(default='csv', help_text='The type this report should be sent as, e.g. CSV.', max_length=20, verbose_name='Report Type', choices=[('csv', 'csv')]),
        ),
        migrations.AlterUniqueTogether(
            name='enterprisecustomerreportingconfiguration',
            unique_together=set([('enterprise_customer', 'data_type', 'report_type', 'delivery_method')]),
        ),
    ]
