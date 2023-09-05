# Generated by Django 3.2.20 on 2023-08-24 17:49

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import simple_history.models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enterprise', '0180_chatgptresponse'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalEnterpriseCustomerSsoConfiguration',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('is_removed', models.BooleanField(default=False)),
                ('uuid', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False)),
                ('active', models.BooleanField(default=False, help_text='Specifies whether the integration with the SSO orchestration is active.')),
                ('identity_provider', models.CharField(help_text='The identity provider integrated with by the SSO orchestrator .', max_length=255)),
                ('metadata_url', models.CharField(help_text='The metadata url of the identity provider.', max_length=255)),
                ('metadata_xml', models.TextField(blank=True, help_text='The metadata xml of the identity provider.', null=True)),
                ('entity_id', models.CharField(help_text='The entity id of the identity provider.', max_length=255)),
                ('update_from_metadata', models.BooleanField(default=True, help_text="Specifies whether the integration with the customer's identity provider should auto update metadata.")),
                ('user_id_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('full_name_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('last_name_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('email_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('username_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('country_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('submitted_at', models.DateTimeField(blank=True, help_text='The date and time when the configuration was submitted to the SSO orchestration.', null=True)),
                ('configured_at', models.DateTimeField(blank=True, help_text='The date and time when the configuration was completed by the SSO orchestration.', null=True)),
                ('validated_at', models.DateTimeField(blank=True, help_text='The date and time when the configuration was validated and used for the first time.', null=True)),
                ('odata_api_timeout_interval', models.PositiveIntegerField(blank=True, default=29, help_text='SAP specific configuration: the timeout interval for the OData API in seconds.', null=True)),
                ('odata_api_root_url', models.CharField(blank=True, help_text='SAP specific configuration: the root url of the OData API.', max_length=255, null=True)),
                ('odata_company_id', models.CharField(blank=True, help_text='SAP specific configuration: the company id of the OData API.', max_length=255, null=True)),
                ('sapsf_oauth_root_url', models.CharField(blank=True, help_text='SAP specific configuration: the root url of the SAP SuccessFactors OAuth API.', max_length=255, null=True)),
                ('odata_api_request_timeout', models.PositiveIntegerField(blank=True, default=29, help_text='SAP specific configuration: the timeout interval for the OData API in seconds.', null=True)),
                ('sapsf_private_key', models.TextField(blank=True, help_text='SAP specific configuration: the private key used to sign the SAML assertion.', null=True)),
                ('odata_client_id', models.CharField(blank=True, help_text='SAP specific configuration: the client id of the OData API.', max_length=255, null=True)),
                ('oauth_user_id', models.CharField(blank=True, help_text='SAP specific configuration: the user id of the OAuth API.', max_length=255, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('enterprise_customer', models.ForeignKey(blank=True, db_constraint=False, help_text='The enterprise that can be linked using this key.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='enterprise.enterprisecustomer')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical Enterprise Customer SSO Configuration',
                'verbose_name_plural': 'historical Enterprise Customer SSO Configurations',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='EnterpriseCustomerSsoConfiguration',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('is_removed', models.BooleanField(default=False)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('active', models.BooleanField(default=False, help_text='Specifies whether the integration with the SSO orchestration is active.')),
                ('identity_provider', models.CharField(help_text='The identity provider integrated with by the SSO orchestrator .', max_length=255)),
                ('metadata_url', models.CharField(help_text='The metadata url of the identity provider.', max_length=255)),
                ('metadata_xml', models.TextField(blank=True, help_text='The metadata xml of the identity provider.', null=True)),
                ('entity_id', models.CharField(help_text='The entity id of the identity provider.', max_length=255)),
                ('update_from_metadata', models.BooleanField(default=True, help_text="Specifies whether the integration with the customer's identity provider should auto update metadata.")),
                ('user_id_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('full_name_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('last_name_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('email_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('username_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('country_attribute', models.CharField(blank=True, max_length=128, null=True)),
                ('submitted_at', models.DateTimeField(blank=True, help_text='The date and time when the configuration was submitted to the SSO orchestration.', null=True)),
                ('configured_at', models.DateTimeField(blank=True, help_text='The date and time when the configuration was completed by the SSO orchestration.', null=True)),
                ('validated_at', models.DateTimeField(blank=True, help_text='The date and time when the configuration was validated and used for the first time.', null=True)),
                ('odata_api_timeout_interval', models.PositiveIntegerField(blank=True, default=29, help_text='SAP specific configuration: the timeout interval for the OData API in seconds.', null=True)),
                ('odata_api_root_url', models.CharField(blank=True, help_text='SAP specific configuration: the root url of the OData API.', max_length=255, null=True)),
                ('odata_company_id', models.CharField(blank=True, help_text='SAP specific configuration: the company id of the OData API.', max_length=255, null=True)),
                ('sapsf_oauth_root_url', models.CharField(blank=True, help_text='SAP specific configuration: the root url of the SAP SuccessFactors OAuth API.', max_length=255, null=True)),
                ('odata_api_request_timeout', models.PositiveIntegerField(blank=True, default=29, help_text='SAP specific configuration: the timeout interval for the OData API in seconds.', null=True)),
                ('sapsf_private_key', models.TextField(blank=True, help_text='SAP specific configuration: the private key used to sign the SAML assertion.', null=True)),
                ('odata_client_id', models.CharField(blank=True, help_text='SAP specific configuration: the client id of the OData API.', max_length=255, null=True)),
                ('oauth_user_id', models.CharField(blank=True, help_text='SAP specific configuration: the user id of the OAuth API.', max_length=255, null=True)),
                ('enterprise_customer', models.ForeignKey(help_text='The enterprise that can be linked using this key.', on_delete=django.db.models.deletion.CASCADE, related_name='sso_orchestration_records', to='enterprise.enterprisecustomer')),
            ],
            options={
                'verbose_name': 'Enterprise Customer SSO Configuration',
                'verbose_name_plural': 'Enterprise Customer SSO Configurations',
            },
        ),
        migrations.AlterModelManagers(
            name='enterprisecustomerssoconfiguration',
            managers=[
                ('all_objects', django.db.models.manager.Manager()),
            ],
        ),
    ]
