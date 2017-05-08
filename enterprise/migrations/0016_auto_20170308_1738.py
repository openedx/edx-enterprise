# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0015_auto_20170130_0003'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomer',
            name='contact_email',
            field=models.EmailField(help_text='Optional contact email that is displayed to learners.', max_length=254, blank=True),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='contact_email',
            field=models.EmailField(help_text='Optional contact email that is displayed to learners.', max_length=254, blank=True),
        ),
    ]
