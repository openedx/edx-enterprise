# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import model_utils.fields

import consent.mixins


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0024_enterprisecustomercatalog_historicalenterprisecustomercatalog'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DataSharingConsent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('username', models.CharField(help_text='Name of the user whose consent state is stored.', max_length=255)),
                ('granted', models.NullBooleanField(help_text='Whether consent is granted.')),
                ('course_id', models.CharField(help_text='Course key for which data sharing consent is granted.', max_length=255)),
                ('enterprise_customer', models.ForeignKey(related_name='enterprise_customer_consent', to='enterprise.EnterpriseCustomer', on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Data Sharing Consent Record',
                'verbose_name_plural': 'Data Sharing Consent Records',
            },
            bases=(consent.mixins.ConsentModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalDataSharingConsent',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('username', models.CharField(help_text='Name of the user whose consent state is stored.', max_length=255)),
                ('granted', models.NullBooleanField(help_text='Whether consent is granted.')),
                ('course_id', models.CharField(help_text='Course key for which data sharing consent is granted.', max_length=255)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('enterprise_customer', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='enterprise.EnterpriseCustomer', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Data Sharing Consent Record',
            },
        ),
        migrations.AlterUniqueTogether(
            name='datasharingconsent',
            unique_together=set([('enterprise_customer', 'username', 'course_id')]),
        ),
    ]
