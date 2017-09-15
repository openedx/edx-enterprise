# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0025_auto_20170828_1412'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicaluserdatasharingconsentaudit',
            name='history_user',
        ),
        migrations.RemoveField(
            model_name='historicaluserdatasharingconsentaudit',
            name='user',
        ),
        migrations.RemoveField(
            model_name='userdatasharingconsentaudit',
            name='user',
        ),
        migrations.RemoveField(
            model_name='enterprisecourseenrollment',
            name='consent_granted',
        ),
        migrations.RemoveField(
            model_name='enterprisecustomer',
            name='require_account_level_consent',
        ),
        migrations.RemoveField(
            model_name='historicalenterprisecourseenrollment',
            name='consent_granted',
        ),
        migrations.RemoveField(
            model_name='historicalenterprisecustomer',
            name='require_account_level_consent',
        ),
        migrations.DeleteModel(
            name='HistoricalUserDataSharingConsentAudit',
        ),
        migrations.DeleteModel(
            name='UserDataSharingConsentAudit',
        ),
    ]
