# Generated by Django 3.2.11 on 2022-02-10 15:46

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    # Commenting out `replaces` to allow --prune to function correctly and clean up the migrations table.
    # replaces = [('sap_success_factors', '0001_squashed_0022_auto_20200206_1046'), ('sap_success_factors', '0002_sapsuccessfactorslearnerdatatransmissionaudit_credit_hours'), ('sap_success_factors', '0003_auto_20210701_1556'), ('sap_success_factors', '0004_auto_20210708_1639'), ('sap_success_factors', '0005_sapsuccessfactorsenterprisecustomerconfiguration_prevent_learner_self_submit_grades'), ('sap_success_factors', '0006_sapsuccessfactorsenterprisecustomerconfiguration_idp_id'), ('sap_success_factors', '0007_sapsuccessfactorsenterprisecustomerconfiguration_disable_learner_data_transmissions'), ('sap_success_factors', '0008_alter_sapsuccessfactorsenterprisecustomerconfiguration_enterprise_customer'), ('sap_success_factors', '0009_auto_20220126_1837'), ('sap_success_factors', '0010_sapsuccessfactorsenterprisecustomerconfiguration_display_name'), ('sap_success_factors', '0011_alter_sapsuccessfactorslearnerdatatransmissionaudit_enterprise_course_enrollment_id')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enterprise', '0094_add_use_enterprise_catalog_sample'),
        ('enterprise', '0151_add_is_active_to_invite_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='SAPSuccessFactorsGlobalConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('completion_status_api_path', models.CharField(max_length=255)),
                ('course_api_path', models.CharField(max_length=255)),
                ('oauth_api_path', models.CharField(max_length=255)),
                ('search_student_api_path', models.CharField(max_length=255)),
                ('provider_id', models.CharField(default='EDX', max_length=100)),
                ('changed_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Changed by')),
            ],
        ),
        migrations.CreateModel(
            name='SAPSuccessFactorsEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=1, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('channel_worker_username', models.CharField(blank=True, default='', help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255)),
                ('catalogs_to_transmit', models.TextField(blank=True, default='', help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.')),
                ('key', models.CharField(blank=True, default='', help_text='OAuth client identifier.', max_length=255, verbose_name='Client ID')),
                ('sapsf_base_url', models.CharField(blank=True, default='', help_text='Base URL of success factors API.', max_length=255, verbose_name='SAP Base URL')),
                ('sapsf_company_id', models.CharField(blank=True, default='', help_text='Success factors company identifier.', max_length=255, verbose_name='SAP Company ID')),
                ('sapsf_user_id', models.CharField(blank=True, default='', help_text='Success factors user identifier.', max_length=255, verbose_name='SAP User ID')),
                ('secret', models.CharField(blank=True, default='', help_text='OAuth client secret.', max_length=255, verbose_name='Client Secret')),
                ('user_type', models.CharField(choices=[('user', 'User'), ('admin', 'Admin')], default='user', help_text='Type of SAP User (admin or user).', max_length=20, verbose_name='SAP User Type')),
                ('additional_locales', models.TextField(blank=True, default='', help_text='A comma-separated list of additional locales.', verbose_name='Additional Locales')),
                ('show_course_price', models.BooleanField(default=False)),
                ('transmit_total_hours', models.BooleanField(default=False, help_text='Include totalHours in the transmitted completion data', verbose_name='Transmit Total Hours')),
                ('enterprise_customer', models.ForeignKey(help_text='Enterprise Customer associated with the configuration.', on_delete=django.db.models.deletion.CASCADE, to='enterprise.enterprisecustomer')),
                ('prevent_self_submit_grades', models.BooleanField(default=False, help_text="When set to True, the integration will use the generic edX service user ('sapsf_user_id') defined in the SAP Customer Configuration for course completion.", verbose_name='Prevent Learner From Self-Submitting Grades')),
                ('idp_id', models.CharField(blank=True, default='', help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255)),
                ('disable_learner_data_transmissions', models.BooleanField(default=False, help_text='When set to True, the configured customer will no longer receive learner data transmissions, both scheduled and signal based', verbose_name='Disable Learner Data Transmission')),
                ('display_name', models.CharField(blank=True, default='', help_text='A configuration nickname.', max_length=30)),
            ],
        ),
        migrations.CreateModel(
            name='SapSuccessFactorsLearnerDataTransmissionAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sapsf_user_id', models.CharField(max_length=255)),
                ('enterprise_course_enrollment_id', models.IntegerField(db_index=True)),
                ('course_id', models.CharField(max_length=255)),
                ('course_completed', models.BooleanField(default=True)),
                ('instructor_name', models.CharField(blank=True, max_length=255)),
                ('grade', models.CharField(max_length=100)),
                ('total_hours', models.FloatField(blank=True, null=True)),
                ('completed_timestamp', models.BigIntegerField()),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('credit_hours', models.FloatField(blank=True, null=True)),
            ],
        ),
    ]
