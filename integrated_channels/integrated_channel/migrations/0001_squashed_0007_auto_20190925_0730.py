# Generated by Django 2.2.12 on 2020-04-21 20:42

import jsonfield.fields

import django.utils.timezone
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('enterprise', '0094_add_use_enterprise_catalog_sample'),
    ]

    operations = [
        migrations.CreateModel(
            name='LearnerDataTransmissionAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enterprise_course_enrollment_id', models.PositiveIntegerField(db_index=True)),
                ('course_id', models.CharField(max_length=255)),
                ('course_completed', models.BooleanField(default=True)),
                ('completed_timestamp', models.BigIntegerField()),
                ('instructor_name', models.CharField(blank=True, max_length=255)),
                ('grade', models.CharField(max_length=100)),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ContentMetadataItemTransmission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('integrated_channel_code', models.CharField(max_length=30)),
                ('content_id', models.CharField(max_length=255)),
                ('channel_metadata', jsonfield.fields.JSONField(dump_kwargs={'cls': jsonfield.encoder.JSONEncoder, 'separators': (',', ':')}, load_kwargs={})),
                ('enterprise_customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='enterprise.EnterpriseCustomer')),
            ],
            options={
                'unique_together': {('enterprise_customer', 'integrated_channel_code', 'content_id')},
            },
        ),
    ]
