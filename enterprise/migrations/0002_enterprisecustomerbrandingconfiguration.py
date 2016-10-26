# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.utils.timezone
from django.db import migrations, models

import model_utils.fields

import enterprise.models
import enterprise.validators


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnterpriseCustomerBrandingConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('logo', models.ImageField(validators=[enterprise.validators.validate_image_extension, enterprise.validators.validate_image_size], upload_to=enterprise.models.logo_path, max_length=255, blank=True, help_text='Please add only .PNG files for logo images.', null=True)),
                ('enterprise_customer', models.OneToOneField(to='enterprise.EnterpriseCustomer')),
            ],
            options={
                'verbose_name': 'Enterprise Customer Branding',
                'verbose_name_plural': 'Enterprise Customer Brandings',
            },
        ),
    ]
