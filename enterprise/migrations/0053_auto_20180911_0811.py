# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0052_create_unique_slugs'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomer',
            name='country',
            field=django_countries.fields.CountryField(max_length=2, null=True),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='country',
            field=django_countries.fields.CountryField(max_length=2, null=True),
        ),
    ]
