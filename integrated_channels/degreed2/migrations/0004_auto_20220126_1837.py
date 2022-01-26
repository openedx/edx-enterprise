# Generated by Django 3.2.11 on 2022-01-26 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed2', '0003_alter_degreed2enterprisecustomerconfiguration_enterprise_customer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='catalogs_to_transmit',
            field=models.TextField(blank=True, default='', help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.'),
        ),
        migrations.AlterField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='channel_worker_username',
            field=models.CharField(blank=True, default='', help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255),
        ),
        migrations.AlterField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='client_id',
            field=models.CharField(blank=True, default='', help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID'),
        ),
        migrations.AlterField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='client_secret',
            field=models.CharField(blank=True, default='', help_text='The API Client Secret provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret'),
        ),
        migrations.AlterField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='degreed_base_url',
            field=models.CharField(blank=True, default='', help_text='The base URL used for API requests to Degreed, i.e. https://degreed.com.', max_length=255, verbose_name='Degreed Base URL'),
        ),
        migrations.AlterField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='degreed_token_fetch_base_url',
            field=models.CharField(blank=True, default='', help_text='If provided, will be used as base url instead of degreed_base_url to fetch tokens', max_length=255, verbose_name='Degreed token fetch base url'),
        ),
        migrations.AlterField(
            model_name='degreed2enterprisecustomerconfiguration',
            name='idp_id',
            field=models.CharField(blank=True, default='', help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='catalogs_to_transmit',
            field=models.TextField(blank=True, default='', help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.'),
        ),
        migrations.AlterField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='channel_worker_username',
            field=models.CharField(blank=True, default='', help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='client_id',
            field=models.CharField(blank=True, default='', help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID'),
        ),
        migrations.AlterField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='client_secret',
            field=models.CharField(blank=True, default='', help_text='The API Client Secret provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret'),
        ),
        migrations.AlterField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='degreed_base_url',
            field=models.CharField(blank=True, default='', help_text='The base URL used for API requests to Degreed, i.e. https://degreed.com.', max_length=255, verbose_name='Degreed Base URL'),
        ),
        migrations.AlterField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='degreed_token_fetch_base_url',
            field=models.CharField(blank=True, default='', help_text='If provided, will be used as base url instead of degreed_base_url to fetch tokens', max_length=255, verbose_name='Degreed token fetch base url'),
        ),
        migrations.AlterField(
            model_name='historicaldegreed2enterprisecustomerconfiguration',
            name='idp_id',
            field=models.CharField(blank=True, default='', help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255),
        ),
    ]
