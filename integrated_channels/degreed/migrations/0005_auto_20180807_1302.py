# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0004_auto_20180306_1251'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='degreedglobalconfiguration',
            name='degreed_base_url',
        ),
        migrations.RemoveField(
            model_name='degreedglobalconfiguration',
            name='degreed_user_id',
        ),
        migrations.RemoveField(
            model_name='degreedglobalconfiguration',
            name='degreed_user_password',
        ),
        migrations.RemoveField(
            model_name='degreedglobalconfiguration',
            name='provider_id',
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='degreed_base_url',
            field=models.CharField(help_text='The base URL used for API requests to Degreed, i.e. https://degreed.com.', max_length=255, verbose_name='Degreed Base URL', blank=True),
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='degreed_user_id',
            field=models.CharField(help_text='The Degreed User ID provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User ID', blank=True),
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='degreed_user_password',
            field=models.CharField(help_text='The Degreed User Password provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User Password', blank=True),
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='provider_id',
            field=models.CharField(default='EDX', help_text='The provider code that Degreed gives to the content provider.', max_length=100, verbose_name='Provider Code'),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='degreed_base_url',
            field=models.CharField(help_text='The base URL used for API requests to Degreed, i.e. https://degreed.com.', max_length=255, verbose_name='Degreed Base URL', blank=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='degreed_user_id',
            field=models.CharField(help_text='The Degreed User ID provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User ID', blank=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='degreed_user_password',
            field=models.CharField(help_text='The Degreed User Password provided to the content provider by Degreed. It is required for getting the OAuth access token.', max_length=255, verbose_name='Degreed User Password', blank=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='provider_id',
            field=models.CharField(default='EDX', help_text='The provider code that Degreed gives to the content provider.', max_length=100, verbose_name='Provider Code'),
        ),
    ]
