# Generated by Django 3.2.20 on 2023-10-11 09:15

from django.db import migrations
from integrated_channels.utils import dummy_reverse
import fernet_fields.fields


def populate_decrypted_fields(apps, schema_editor):
    """
    Populates the encryption fields with the data previously stored in database.
    """
    BlackboardEnterpriseCustomerConfiguration = apps.get_model('blackboard', 'BlackboardEnterpriseCustomerConfiguration')

    for blackboard_enterprise_configuration in BlackboardEnterpriseCustomerConfiguration.objects.all():
        blackboard_enterprise_configuration.decrypted_client_id = blackboard_enterprise_configuration.client_id
        blackboard_enterprise_configuration.decrypted_client_secret = blackboard_enterprise_configuration.client_secret
        blackboard_enterprise_configuration.save()


class Migration(migrations.Migration):

    dependencies = [
        ('blackboard', '0017_alter_historicalblackboardenterprisecustomerconfiguration_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='decrypted_client_id',
            field=fernet_fields.fields.EncryptedCharField(blank=True, default='', help_text='The API Client ID (encrypted at db level) provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID encrypted at db level'),
        ),
        migrations.AddField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='decrypted_client_secret',
            field=fernet_fields.fields.EncryptedCharField(blank=True, default='', help_text='The API Client Secret (encrypted at db level) provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret encrypted at db level'),
        ),
        migrations.AddField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='decrypted_client_id',
            field=fernet_fields.fields.EncryptedCharField(blank=True, default='', help_text='The API Client ID (encrypted at db level) provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID encrypted at db level'),
        ),
        migrations.AddField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='decrypted_client_secret',
            field=fernet_fields.fields.EncryptedCharField(blank=True, default='', help_text='The API Client Secret (encrypted at db level) provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret encrypted at db level'),
        ),
        migrations.RunPython(populate_decrypted_fields, dummy_reverse),
    ]
