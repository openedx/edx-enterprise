# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.utils.timezone
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0009_auto_20161130_1651'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingEnrollment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('course_id', models.CharField(max_length=255)),
                ('course_mode', models.CharField(max_length=25)),
                ('user', models.ForeignKey(to='enterprise.PendingEnterpriseCustomerUser')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='pendingenrollment',
            unique_together=set([('user', 'course_id')]),
        ),
    ]
