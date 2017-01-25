# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enterprise', '0012_auto_20170125_1033'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnterpriseCourseEnrollment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('consent_granted', models.NullBooleanField(help_text='Whether the learner has granted consent for this particular course.')),
                ('course_id', models.CharField(help_text='The course ID in which the learner was enrolled.', max_length=255)),
                ('enterprise_customer_user', models.ForeignKey(related_name='enterprise_enrollments', to='enterprise.EnterpriseCustomerUser', help_text='The enterprise learner to which this enrollment is attached.')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalEnterpriseCourseEnrollment',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('consent_granted', models.NullBooleanField(help_text='Whether the learner has granted consent for this particular course.')),
                ('course_id', models.CharField(help_text='The course ID in which the learner was enrolled.', max_length=255)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('enterprise_customer_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='enterprise.EnterpriseCustomerUser', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical enterprise course enrollment',
            },
        ),
        migrations.AlterUniqueTogether(
            name='enterprisecourseenrollment',
            unique_together=set([('enterprise_customer_user', 'course_id')]),
        ),
    ]
