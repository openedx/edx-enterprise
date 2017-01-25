# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0011_enterprisecustomerentitlement_historicalenterprisecustomerentitlement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomer',
            name='catalog',
            field=models.PositiveIntegerField(help_text='Course catalog for the Enterprise Customer.', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomer',
            name='catalog',
            field=models.PositiveIntegerField(help_text='Course catalog for the Enterprise Customer.', null=True, blank=True),
        ),
    ]
