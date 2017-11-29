# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.utils.timezone
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('integrated_channel', '0002_delete_enterpriseintegratedchannel'),
        ('sap_success_factors', '0010_move_audit_tables_to_base_integrated_channel')
    ]

    state_operations = [
        # Recall from SAPSF's 0009 migration, that we're just changing table name for this one,
        # so since we already altered the table name from SAPSF's 0009, we set model state here.
        migrations.CreateModel(
            name='CatalogTransmissionAudit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created',
                 model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created',
                                                     editable=False)),
                ('modified',
                 model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified',
                                                          editable=False)),
                ('enterprise_customer_uuid', models.UUIDField()),
                ('total_courses', models.PositiveIntegerField()),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('audit_summary', models.TextField(default='{}')),
            ],
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations),
        migrations.CreateModel(
            name='LearnerDataTransmissionAudit',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('enterprise_course_enrollment_id', models.PositiveIntegerField()),
                ('course_id', models.CharField(max_length=255)),
                ('course_completed', models.BooleanField(default=True)),
                ('completed_timestamp', models.BigIntegerField()),
                ('instructor_name', models.CharField(max_length=255, blank=True)),
                ('grade', models.CharField(max_length=100)),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
