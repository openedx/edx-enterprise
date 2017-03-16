# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0015_auto_20170130_0003'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomeruser',
            name='active',
            field=models.BooleanField(default=True),
        ),
    ]
