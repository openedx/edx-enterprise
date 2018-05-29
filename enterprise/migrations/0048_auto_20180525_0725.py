# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0047_auto_20180517_0457'),
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
