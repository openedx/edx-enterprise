# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0003_auto_20180109_0712'),
    ]

    operations = [
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='transmission_chunk_size',
            field=models.IntegerField(default=500, help_text='The maximum number of data items to transmit to the integrated channel with each request.'),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='transmission_chunk_size',
            field=models.IntegerField(default=500, help_text='The maximum number of data items to transmit to the integrated channel with each request.'),
        ),
    ]
