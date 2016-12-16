# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-12-05 04:33
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enterprise', '0009_auto_20161130_1651'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnterpriseCustomerEntitlement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('entitlement_id', models.PositiveIntegerField(help_text="Enterprise customer's entitlement id for relationship with Ecommerce coupon.")),
                ('enterprise_customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enterprise_customer_entitlement', to='enterprise.EnterpriseCustomer')),
            ],
            options={
                'verbose_name': 'Enterprise Customer Entitlement',
                'verbose_name_plural': 'Enterprise Customer Entitlements',
            },
        ),
        migrations.CreateModel(
            name='HistoricalEnterpriseCustomerEntitlement',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('entitlement_id', models.PositiveIntegerField(help_text="Enterprise customer's entitlement id for relationship with Ecommerce coupon.")),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('enterprise_customer', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='enterprise.EnterpriseCustomer')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Enterprise Customer Entitlement',
            },
        ),
    ]
