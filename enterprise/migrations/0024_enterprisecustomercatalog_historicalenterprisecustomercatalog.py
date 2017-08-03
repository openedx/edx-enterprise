# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enterprise', '0023_audit_data_reporting_flag'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnterpriseCustomerCatalog',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', models.UUIDField(default=uuid.uuid4, serialize=False, editable=False, primary_key=True)),
                ('query', models.TextField(help_text='Query to the course discovery service. Leave empty for all results.')),
                ('enterprise_customer', models.ForeignKey(related_name='enterprise_customer_catalog', to='enterprise.EnterpriseCustomer', on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'verbose_name': 'Enterprise Customer Catalog',
                'verbose_name_plural': 'Enterprise Customer Catalogs',
            },
        ),
        migrations.CreateModel(
            name='HistoricalEnterpriseCustomerCatalog',
            fields=[
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)),
                ('query', models.TextField(help_text='Query to the course discovery service. Leave empty for all results.')),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('enterprise_customer', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='enterprise.EnterpriseCustomer', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Enterprise Customer Catalog',
            },
        ),
    ]
