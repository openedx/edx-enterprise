# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import jsonfield.fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0024_enterprisecustomercatalog_historicalenterprisecustomercatalog'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='enterprisecustomercatalog',
            name='query',
        ),
        migrations.RemoveField(
            model_name='historicalenterprisecustomercatalog',
            name='query',
        ),
        migrations.AddField(
            model_name='enterprisecustomercatalog',
            name='content_filter',
            field=jsonfield.fields.JSONField(default={}, help_text="Query parameters which will be used to filter the discovery service's search/all endpoint results, specified as a Json object. An empty Json object means that all available content items will be included in the catalog.", null=True, blank=True),
        ),
        migrations.AddField(
            model_name='enterprisecustomercatalog',
            name='title',
            field=models.CharField(default='All Content', max_length=20),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomercatalog',
            name='content_filter',
            field=jsonfield.fields.JSONField(default={}, help_text="Query parameters which will be used to filter the discovery service's search/all endpoint results, specified as a Json object. An empty Json object means that all available content items will be included in the catalog.", null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomercatalog',
            name='title',
            field=models.CharField(default='All Content', max_length=20),
        ),
    ]
