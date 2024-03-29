# Generated by Django 3.2.11 on 2022-01-26 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0013_alter_degreedenterprisecustomerconfiguration_enterprise_customer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='catalogs_to_transmit',
            field=models.TextField(blank=True, default='', help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.'),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='channel_worker_username',
            field=models.CharField(blank=True, default='', help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='degreed_base_url',
            field=models.CharField(blank=True, default='', help_text='The base URL used for API requests to Degreed, i.e. https://degreed.com.', max_length=255, verbose_name='Degreed Base URL'),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='degreed_company_id',
            field=models.CharField(blank=True, default='', help_text='The organization code provided to the enterprise customer by Degreed.', max_length=255, verbose_name='Degreed Organization Code'),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='degreed_user_id',
            field=models.CharField(blank=True, default='', help_text='The Degreed User ID provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User ID'),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='degreed_user_password',
            field=models.CharField(blank=True, default='', help_text='The Degreed User Password provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User Password'),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='idp_id',
            field=models.CharField(blank=True, default='', help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='key',
            field=models.CharField(blank=True, default='', help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID'),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='secret',
            field=models.CharField(blank=True, default='', help_text='The API Client Secret provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret'),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='catalogs_to_transmit',
            field=models.TextField(blank=True, default='', help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.'),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='channel_worker_username',
            field=models.CharField(blank=True, default='', help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='degreed_base_url',
            field=models.CharField(blank=True, default='', help_text='The base URL used for API requests to Degreed, i.e. https://degreed.com.', max_length=255, verbose_name='Degreed Base URL'),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='degreed_company_id',
            field=models.CharField(blank=True, default='', help_text='The organization code provided to the enterprise customer by Degreed.', max_length=255, verbose_name='Degreed Organization Code'),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='degreed_user_id',
            field=models.CharField(blank=True, default='', help_text='The Degreed User ID provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User ID'),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='degreed_user_password',
            field=models.CharField(blank=True, default='', help_text='The Degreed User Password provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User Password'),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='idp_id',
            field=models.CharField(blank=True, default='', help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='key',
            field=models.CharField(blank=True, default='', help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client ID'),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='secret',
            field=models.CharField(blank=True, default='', help_text='The API Client Secret provided to edX by the enterprise customer to be used to make API calls to Degreed on behalf of the customer.', max_length=255, verbose_name='API Client Secret'),
        ),
    ]
