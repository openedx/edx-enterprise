# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import jsonfield.fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0052_create_unique_slugs'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomercatalog',
            name='content_filter',
            field=jsonfield.fields.JSONField(default={'partner': 'edx', 'level_type': ['Introductory', 'Intermediate', 'Advanced'], 'content_type': 'course'}, help_text="Query parameters which will be used to filter the discovery service's search/all endpoint results, specified as a Json object. An empty Json object means that all available content items will be included in the catalog.", null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomercatalog',
            name='content_filter',
            field=jsonfield.fields.JSONField(default={'partner': 'edx', 'level_type': ['Introductory', 'Intermediate', 'Advanced'], 'content_type': 'course'}, help_text="Query parameters which will be used to filter the discovery service's search/all endpoint results, specified as a Json object. An empty Json object means that all available content items will be included in the catalog.", null=True, blank=True),
        ),
    ]
