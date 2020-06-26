# -*- coding: utf-8 -*-


import multi_email_field.fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0040_auto_20180129_1428'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomerreportingconfiguration',
            name='email',
            field=multi_email_field.fields.MultiEmailField(help_text='The email(s), one per line, where the report should be sent.', verbose_name='Email', blank=True),
        ),
    ]
