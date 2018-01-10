# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0036_sftp_reporting_support'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomerentitlement',
            name='entitlement_id',
            field=models.PositiveIntegerField(help_text="Enterprise customer's entitlement id for relationship with e-commerce coupon.", unique=True, verbose_name='Seat Entitlement'),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomerentitlement',
            name='entitlement_id',
            field=models.PositiveIntegerField(help_text="Enterprise customer's entitlement id for relationship with e-commerce coupon.", verbose_name='Seat Entitlement', db_index=True),
        ),
    ]
