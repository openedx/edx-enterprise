# -*- coding: utf-8 -*-


import django_countries.fields

from django.db import migrations, models


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
