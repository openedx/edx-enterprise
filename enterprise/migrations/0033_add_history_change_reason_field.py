# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0032_reporting_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalenrollmentnotificationemailtemplate',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='historicalenterprisecourseenrollment',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomercatalog',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomerentitlement',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
