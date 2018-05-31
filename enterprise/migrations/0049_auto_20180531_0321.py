# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0048_enterprisecustomeruser_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomercatalog',
            name='title',
            field=models.CharField(default='All Content', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomercatalog',
            name='title',
            field=models.CharField(default='All Content', max_length=255),
        ),
    ]
