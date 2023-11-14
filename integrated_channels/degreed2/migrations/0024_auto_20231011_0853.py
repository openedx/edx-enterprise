# Generated by Django 3.2.20 on 2023-10-11 08:53

from django.db import migrations
from integrated_channels.utils import dummy_reverse
import fernet_fields.fields


def populate_decrypted_fields(apps, schema_editor):
    """
    Populates the encryption fields with the data previously stored in database.
    """
    Degreed2EnterpriseCustomerConfiguration = apps.get_model('degreed2', 'Degreed2EnterpriseCustomerConfiguration')

    for degreed2_enterprise_configuration in Degreed2EnterpriseCustomerConfiguration.objects.all():
        degreed2_enterprise_configuration.decrypted_client_id = degreed2_enterprise_configuration.client_id
        degreed2_enterprise_configuration.decrypted_client_secret = degreed2_enterprise_configuration.client_secret
        degreed2_enterprise_configuration.save()


class Migration(migrations.Migration):

    dependencies = [
        ('degreed2', '0023_alter_historicaldegreed2enterprisecustomerconfiguration_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='decrypted_client_id',
            field=fernet_fields.fields.EncryptedCharField(blank=True, default='', help_text='The API Client ID (encrypted at db level) provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID encrypted at db level'),
        ),
        migrations.AddField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='decrypted_client_secret',
            field=fernet_fields.fields.EncryptedCharField(blank=True, default='', help_text='The API Client Secret (encrypted at db level) provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret encrypted at db level'),
        ),
        migrations.AddField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='decrypted_client_id',
            field=fernet_fields.fields.EncryptedCharField(blank=True, default='', help_text='The API Client ID (encrypted at db level) provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID encrypted at db level'),
        ),
        migrations.AddField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='decrypted_client_secret',
            field=fernet_fields.fields.EncryptedCharField(blank=True, default='', help_text='The API Client Secret (encrypted at db level) provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret encrypted at db level'),
        ),
        migrations.RunPython(populate_decrypted_fields, dummy_reverse),
    ]
