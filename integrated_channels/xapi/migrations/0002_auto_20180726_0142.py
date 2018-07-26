# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xapi', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xapilrsconfiguration',
            name='key',
            field=models.CharField(max_length=255, help_text='Key of xAPI LRS.', verbose_name='Client ID'),
        ),
        migrations.AlterField(
            model_name='xapilrsconfiguration',
            name='secret',
            field=models.CharField(max_length=255, help_text='secret of xAPI LRS.', verbose_name='Client Secret'),
        ),
        migrations.AlterField(
            model_name='xapilrsconfiguration',
            name='version',
            field=models.CharField(max_length=16, default='1.0.1', help_text='Version of xAPI.'),
        ),
    ]
