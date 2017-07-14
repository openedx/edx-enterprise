# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0020_auto_20170624_2316'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalenrollmentnotificationemailtemplate',
            name='history_change_reason',
        ),
        migrations.RemoveField(
            model_name='historicalenterprisecourseenrollment',
            name='history_change_reason',
        ),
        migrations.RemoveField(
            model_name='historicalenterprisecustomer',
            name='history_change_reason',
        ),
        migrations.RemoveField(
            model_name='historicalenterprisecustomerentitlement',
            name='history_change_reason',
        ),
        migrations.RemoveField(
            model_name='historicaluserdatasharingconsentaudit',
            name='history_change_reason',
        ),
    ]
