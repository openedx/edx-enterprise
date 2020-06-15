# -*- coding: utf-8 -*-


import jsonfield.fields

import django.utils.timezone
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0041_auto_20180212_1507'),
        ('integrated_channel', '0004_catalogtransmissionaudit_channel'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContentMetadataItemTransmission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('integrated_channel_code', models.CharField(max_length=30)),
                ('content_id', models.CharField(max_length=255)),
                ('channel_metadata', jsonfield.fields.JSONField()),
                ('enterprise_customer', models.ForeignKey(to='enterprise.EnterpriseCustomer', on_delete=models.CASCADE)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='contentmetadataitemtransmission',
            unique_together=set([('enterprise_customer', 'integrated_channel_code', 'content_id')]),
        ),
    ]
