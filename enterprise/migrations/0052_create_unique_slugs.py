# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0051_add_enterprise_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomer',
            name='slug',
            field=models.SlugField(default='default', help_text='A short string uniquely identifying this enterprise. Cannot contain spaces and should be a usable as a CSS class. Examples: "ubc", "mit-staging"', unique=True, max_length=30),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomer',
            name='slug',
            field=models.SlugField(default='default', help_text='A short string uniquely identifying this enterprise. Cannot contain spaces and should be a usable as a CSS class. Examples: "ubc", "mit-staging"', max_length=30),
        ),
    ]
