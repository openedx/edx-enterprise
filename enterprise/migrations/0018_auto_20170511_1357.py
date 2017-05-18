# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0017_auto_20170508_1341'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomer',
            name='enable_audit_enrollment',
            field=models.BooleanField(default=False, help_text='Specifies whether the audit track enrollment option will be displayed in the course enrollment view.'),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='enable_audit_enrollment',
            field=models.BooleanField(default=False, help_text='Specifies whether the audit track enrollment option will be displayed in the course enrollment view.'),
        ),
    ]
