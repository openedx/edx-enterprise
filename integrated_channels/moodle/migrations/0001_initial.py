# Generated by Django 2.2.15 on 2020-08-20 16:06

import simple_history.models

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('enterprise', '0109_remove_use_enterprise_catalog_sample'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MoodleEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=500, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('channel_worker_username', models.CharField(blank=True, help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255, null=True)),
                ('catalogs_to_transmit', models.TextField(blank=True, help_text='A comma-separated list of catalog UUIDs to transmit.', null=True)),
                ('moodle_base_url', models.CharField(blank=True, help_text='The base URL used for API requests to Moodle', max_length=255, verbose_name='Moodle Base URL')),
                ('api_token', models.CharField(help_text='The token used to authenticate to Moodle. Created in Moodle at Site administration/Plugins/Web services/Manage tokens', max_length=100, null=True, verbose_name='Developer Token')),
                ('wsusername', models.CharField(help_text="The API user's username used to obtain new tokens.", max_length=100, verbose_name='Webservice Username')),
                ('wspassword', models.CharField(help_text="The API user's password used to obtain new tokens.", max_length=255, verbose_name='Webservice Password')),
                ('enterprise_customer', models.OneToOneField(help_text='Enterprise Customer associated with the configuration.', on_delete=django.db.models.deletion.CASCADE, to='enterprise.EnterpriseCustomer')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalMoodleEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=500, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('channel_worker_username', models.CharField(blank=True, help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255, null=True)),
                ('catalogs_to_transmit', models.TextField(blank=True, help_text='A comma-separated list of catalog UUIDs to transmit.', null=True)),
                ('moodle_base_url', models.CharField(blank=True, help_text='The base URL used for API requests to Moodle', max_length=255, verbose_name='Moodle Base URL')),
                ('api_token', models.CharField(help_text='The token used to authenticate to Moodle. Created in Moodle at Site administration/Plugins/Web services/Manage tokens', max_length=100, null=True, verbose_name='Developer Token')),
                ('wsusername', models.CharField(help_text="The API user's username used to obtain new tokens.", max_length=100, verbose_name='Webservice Username')),
                ('wspassword', models.CharField(help_text="The API user's password used to obtain new tokens.", max_length=255, verbose_name='Webservice Password')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('enterprise_customer', models.ForeignKey(blank=True, db_constraint=False, help_text='Enterprise Customer associated with the configuration.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='enterprise.EnterpriseCustomer')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical moodle enterprise customer configuration',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]
