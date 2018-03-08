# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0041_auto_20180212_1507'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CSODWebServicesEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=500, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('csod_lo_ws_base_url', models.CharField(help_text="The LO Web Services domain of the customer's CSOD Instance.", max_length=255, verbose_name='CSOD Learning Object Web Services base URL', blank=True)),
                ('csod_lms_ws_base_url', models.CharField(help_text="The LMS Web Services domain of the customer's CSOD Instance.", max_length=255, verbose_name='CSOD LMS Web Services base URL', blank=True)),
                ('csod_username', models.CharField(help_text="The CSOD Username provided to the customer's Cornerstone instance. It is required for authenticating with their SOAP API.", max_length=255, verbose_name='CSOD Username', blank=True)),
                ('csod_user_password', models.CharField(help_text='The Degreed User Password provided to the content provider by Degreed. It is required for authenticating with their SOAP API.', max_length=255, verbose_name='Degreed User Password', blank=True)),
                ('provider', models.CharField(default='EDX', help_text="The provider name that is configured for this content provider in the customer's system.", max_length=100, verbose_name='Provider Name')),
                ('key', models.CharField(help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Cornerstone on behalf of the customer.', max_length=255, verbose_name='API Client ID', blank=True)),
                ('secret', models.CharField(help_text='The API Client Secret provided to edX by the enterprise customer to be used to make API calls to Cornerstone on behalf of the customer.', max_length=255, verbose_name='API Client Secret', blank=True)),
                ('enterprise_customer', models.OneToOneField(to='enterprise.EnterpriseCustomer', help_text='Enterprise Customer associated with the configuration.')),
            ],
        ),
        migrations.CreateModel(
            name='CSODWebServicesGlobalConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('complete_learning_object_api_path', models.CharField(help_text='The API path for making POST/DELETE requests to mark a user as having completed a LO on CSOD.', max_length=255, verbose_name='Complete Learning Object (LO) API Path')),
                ('create_learning_object_path', models.CharField(help_text='The API path for making course metadata POST requests to create LOs on CSOD.', max_length=255, verbose_name='Create Learning Object (LO) API Path')),
                ('update_learning_object_path', models.CharField(help_text='The API path for making course metadata POST requests to update LOs on CSOD.', max_length=255, verbose_name='Update Learning Object (LO) API Path')),
                ('session_token_api_path', models.CharField(help_text='The API path for making OAuth-related POST requests to Cornerstone. This will be used to gain the OAuth access token and secret which is required for other API calls.', max_length=255, verbose_name='Session Token API Path')),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, editable=False, to=settings.AUTH_USER_MODEL, null=True, verbose_name='Changed by')),
            ],
        ),
        migrations.CreateModel(
            name='CSODWebServicesLearnerDataTransmissionAudit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('csod_username', models.CharField(max_length=255)),
                ('enterprise_course_enrollment_id', models.PositiveIntegerField()),
                ('learning_object_id', models.CharField(help_text='The LO ID which is used to uniquely identify the course for Cornerstone.', max_length=255)),
                ('comment_string', models.CharField(help_text="The comment containing details for a learner's course completion sent to Cornerstone.", max_length=255)),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalCSODWebServicesEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=500, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('csod_lo_ws_base_url', models.CharField(help_text="The LO Web Services domain of the customer's CSOD Instance.", max_length=255, verbose_name='CSOD Learning Object Web Services base URL', blank=True)),
                ('csod_lms_ws_base_url', models.CharField(help_text="The LMS Web Services domain of the customer's CSOD Instance.", max_length=255, verbose_name='CSOD LMS Web Services base URL', blank=True)),
                ('csod_username', models.CharField(help_text="The CSOD Username provided to the customer's Cornerstone instance. It is required for authenticating with their SOAP API.", max_length=255, verbose_name='CSOD Username', blank=True)),
                ('csod_user_password', models.CharField(help_text='The Degreed User Password provided to the content provider by Degreed. It is required for authenticating with their SOAP API.', max_length=255, verbose_name='Degreed User Password', blank=True)),
                ('provider', models.CharField(default='EDX', help_text="The provider name that is configured for this content provider in the customer's system.", max_length=100, verbose_name='Provider Name')),
                ('key', models.CharField(help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Cornerstone on behalf of the customer.', max_length=255, verbose_name='API Client ID', blank=True)),
                ('secret', models.CharField(help_text='The API Client Secret provided to edX by the enterprise customer to be used to make API calls to Cornerstone on behalf of the customer.', max_length=255, verbose_name='API Client Secret', blank=True)),
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
                'verbose_name': 'historical csod web services enterprise customer configuration',
            },
        ),
    ]
