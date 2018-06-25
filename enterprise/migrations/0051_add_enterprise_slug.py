# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.utils.text import slugify


def populate_slug(apps, schema_editor):
    EnterpriseCustomer = apps.get_model('enterprise', 'EnterpriseCustomer')

    enterprises = EnterpriseCustomer.objects.all()
    for enterprise in enterprises:
        enterprise.slug = slugify(enterprise.name)
        enterprise.save()


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0050_progress_v2'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomer',
            name='slug',
            field=models.SlugField(default='default', help_text='A short string uniquely identifying this enterprise. Cannot contain spaces and should be a usable as a CSS class. Examples: "ubc", "mit-staging"', max_length=30, blank=True),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='slug',
            field=models.SlugField(default='default', help_text='A short string uniquely identifying this enterprise. Cannot contain spaces and should be a usable as a CSS class. Examples: "ubc", "mit-staging"', max_length=30, blank=True),
        ),
        migrations.RunPython(populate_slug),
    ]
