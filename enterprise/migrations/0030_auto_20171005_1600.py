# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0029_auto_20170925_1909'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='enrollmentnotificationemailtemplate',
            name='site',
        ),
        migrations.RemoveField(
            model_name='historicalenrollmentnotificationemailtemplate',
            name='site',
        ),
    ]
