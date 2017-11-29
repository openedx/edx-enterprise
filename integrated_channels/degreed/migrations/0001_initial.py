# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0034_auto_20171023_0727'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DegreedEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('active', models.BooleanField()),
                ('key', models.CharField(help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID', blank=True)),
                ('secret', models.CharField(help_text='The API Client Secret provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret', blank=True)),
                ('degreed_company_id', models.CharField(help_text='The organization code provided to the enterprise customer by Degreed.', max_length=255, verbose_name='Degreed Organization Code', blank=True)),
                ('enterprise_customer', models.OneToOneField(to='enterprise.EnterpriseCustomer')),
            ],
        ),
        migrations.CreateModel(
            name='DegreedGlobalConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('degreed_base_url', models.CharField(help_text='The base URL used for API requests to Degreed, i.e. https://degreed.com.', max_length=255, verbose_name='Degreed Base URL')),
                ('completion_status_api_path', models.CharField(help_text='The API path for making completion POST/DELETE requests to Degreed.', max_length=255, verbose_name='Completion Status API Path')),
                ('course_api_path', models.CharField(help_text='The API path for making course metadata POST/DELETE requests to Degreed.', max_length=255, verbose_name='Course Metadata API Path')),
                ('oauth_api_path', models.CharField(help_text='The API path for making OAuth-related POST requests to Degreed. This will be used to gain the OAuth access token which is required for other API calls.', max_length=255, verbose_name='OAuth API Path')),
                ('degreed_user_id', models.CharField(help_text='The Degreed User ID provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User ID', blank=True)),
                ('degreed_user_password', models.CharField(help_text='The Degreed User Password provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User Password', blank=True)),
                ('provider_id', models.CharField(default='EDX', help_text='The provider code that Degreed gives to the content provider.', max_length=100, verbose_name='Provider Code')),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, editable=False, to=settings.AUTH_USER_MODEL, null=True, verbose_name='Changed by')),
            ],
        ),
        migrations.CreateModel(
            name='DegreedLearnerDataTransmissionAudit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('degreed_user_email', models.CharField(max_length=255)),
                ('enterprise_course_enrollment_id', models.PositiveIntegerField()),
                ('course_id', models.CharField(help_text="The course run's key which is used to uniquely identify the course for Degreed.", max_length=255)),
                ('course_completed', models.BooleanField(default=True, help_text="The learner's course completion status transmitted to Degreed.")),
                ('completed_timestamp', models.CharField(help_text='Represents the Degreed representation of a timestamp: yyyy-mm-dd, which is always 10 characters.', max_length=10)),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalDegreedEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('active', models.BooleanField()),
                ('key', models.CharField(help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID', blank=True)),
                ('secret', models.CharField(help_text='The API Client Secret provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret', blank=True)),
                ('degreed_company_id', models.CharField(help_text='The organization code provided to the enterprise customer by Degreed.', max_length=255, verbose_name='Degreed Organization Code', blank=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('enterprise_customer', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='enterprise.EnterpriseCustomer', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical degreed enterprise customer configuration',
            },
        ),
    ]
