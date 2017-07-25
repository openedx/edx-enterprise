# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0022_auto_20170720_1543'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomer',
            name='enable_audit_data_reporting',
            field=models.BooleanField(default=False, help_text='Specifies whether to pass-back audit track enrollment data through an integrated channel.'),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='enable_audit_data_reporting',
            field=models.BooleanField(default=False, help_text='Specifies whether to pass-back audit track enrollment data through an integrated channel.'),
        ),
    ]
