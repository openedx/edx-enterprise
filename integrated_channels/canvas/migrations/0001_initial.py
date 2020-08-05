# Generated by Django 2.2.15 on 2020-08-05 15:40

import simple_history.models

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('enterprise', '0107_remove_branding_config_banner_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalCanvasEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=500, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('channel_worker_username', models.CharField(blank=True, help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255, null=True)),
                ('catalogs_to_transmit', models.TextField(blank=True, help_text='A comma-separated list of catalog UUIDs to transmit.', null=True)),
                ('client_id', models.CharField(help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Canvas on behalf of the customer.', max_length=255, null=True, verbose_name='API Client ID')),
                ('client_secret', models.CharField(help_text='The API Client Secret provided to edX by the enterprise customer to be used to make  API calls to Canvas on behalf of the customer.', max_length=255, null=True, verbose_name='API Client Secret')),
                ('canvas_company_id', models.CharField(blank=True, help_text='The organization code provided to the enterprise customer by Canvas.', max_length=255, null=True, verbose_name='Canvas Organization Code')),
                ('canvas_base_url', models.CharField(blank=True, help_text='The base URL used for API requests to Canvas, i.e. https://instructure.com.', max_length=255, null=True, verbose_name='Canvas Base URL')),
                ('provider_id', models.CharField(default='EDX', help_text='The provider code that Canvas gives to the content provider.', max_length=100, verbose_name='Provider Code')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('enterprise_customer', models.ForeignKey(blank=True, db_constraint=False, help_text='Enterprise Customer associated with the configuration.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='enterprise.EnterpriseCustomer')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical canvas enterprise customer configuration',
                'ordering': ('-history_date', '-history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='CanvasGlobalConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('course_api_path', models.CharField(help_text='The API path for making course metadata POST/DELETE requests to Canvas.', max_length=255, verbose_name='Course Metadata API Path')),
                ('oauth_api_path', models.CharField(default='login/oauth2/token', help_text='The API path for making OAuth-related POST requests to Canvas. This will be used to gain the OAuth access token for other API calls.', max_length=255, verbose_name='OAuth API Path')),
                ('changed_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Changed by')),
            ],
        ),
        migrations.CreateModel(
            name='CanvasEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=500, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('channel_worker_username', models.CharField(blank=True, help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255, null=True)),
                ('catalogs_to_transmit', models.TextField(blank=True, help_text='A comma-separated list of catalog UUIDs to transmit.', null=True)),
                ('client_id', models.CharField(help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Canvas on behalf of the customer.', max_length=255, null=True, verbose_name='API Client ID')),
                ('client_secret', models.CharField(help_text='The API Client Secret provided to edX by the enterprise customer to be used to make  API calls to Canvas on behalf of the customer.', max_length=255, null=True, verbose_name='API Client Secret')),
                ('canvas_company_id', models.CharField(blank=True, help_text='The organization code provided to the enterprise customer by Canvas.', max_length=255, null=True, verbose_name='Canvas Organization Code')),
                ('canvas_base_url', models.CharField(blank=True, help_text='The base URL used for API requests to Canvas, i.e. https://instructure.com.', max_length=255, null=True, verbose_name='Canvas Base URL')),
                ('provider_id', models.CharField(default='EDX', help_text='The provider code that Canvas gives to the content provider.', max_length=100, verbose_name='Provider Code')),
                ('enterprise_customer', models.OneToOneField(help_text='Enterprise Customer associated with the configuration.', on_delete=django.db.models.deletion.CASCADE, to='enterprise.EnterpriseCustomer')),
            ],
        ),
    ]
