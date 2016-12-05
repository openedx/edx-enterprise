# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enterprise', '0008_auto_20161124_2355'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalUserDataSharingConsentAudit',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('state', models.CharField(default='not_set', help_text='Stores whether the user linked to this model has consented to have their information shared with the linked EnterpriseCustomer.', max_length=8, choices=[('not_set', 'Not set'), ('enabled', 'Enabled'), ('disabled', 'Disabled')])),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='enterprise.EnterpriseCustomerUser', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Data Sharing Consent Audit State',
            },
        ),
        migrations.CreateModel(
            name='UserDataSharingConsentAudit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('state', models.CharField(default='not_set', help_text='Stores whether the user linked to this model has consented to have their information shared with the linked EnterpriseCustomer.', max_length=8, choices=[('not_set', 'Not set'), ('enabled', 'Enabled'), ('disabled', 'Disabled')])),
                ('user', models.ForeignKey(to='enterprise.EnterpriseCustomerUser')),
            ],
            options={
                'verbose_name': 'Data Sharing Consent Audit State',
                'verbose_name_plural': 'Data Sharing Consent Audit States',
            },
        ),
        migrations.AddField(
            model_name='enterprisecustomer',
            name='enable_data_sharing_consent',
            field=models.BooleanField(default=False, help_text='This field is used to determine whether data sharing consent is enabled or disabled for users signing in using this enterprise customer. If disabled, consent will not be requested, and eligible data will not be shared.'),
        ),
        migrations.AddField(
            model_name='enterprisecustomer',
            name='enforce_data_sharing_consent',
            field=models.CharField(default='optional', help_text="This field determines if data sharing consent is optional, if it's required at login, or if it's required when registering for eligible courses.", max_length=25, choices=[('optional', 'Optional'), ('at_login', 'At Login'), ('at_enrollment', 'At Enrollment')]),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='enable_data_sharing_consent',
            field=models.BooleanField(default=False, help_text='This field is used to determine whether data sharing consent is enabled or disabled for users signing in using this enterprise customer. If disabled, consent will not be requested, and eligible data will not be shared.'),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='enforce_data_sharing_consent',
            field=models.CharField(default='optional', help_text="This field determines if data sharing consent is optional, if it's required at login, or if it's required when registering for eligible courses.", max_length=25, choices=[('optional', 'Optional'), ('at_login', 'At Login'), ('at_enrollment', 'At Enrollment')]),
        ),
    ]
