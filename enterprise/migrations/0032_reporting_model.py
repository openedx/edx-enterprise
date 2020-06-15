# -*- coding: utf-8 -*-


import django.core.validators
import django.utils.timezone
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0031_auto_20171012_1249'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnterpriseCustomerReportingConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('active', models.BooleanField(verbose_name='Active')),
                ('delivery_method', models.CharField(default='email', help_text='The method in which the data should be sent.', max_length=20, verbose_name='Delivery Method', choices=[('email', 'email'), ('ftp', 'ftp')])),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('frequency', models.CharField(default='monthly', help_text='The frequency interval (daily, weekly, or monthly) that the report should be sent.', max_length=20, verbose_name='Frequency', choices=[('daily', 'daily'), ('monthly', 'monthly'), ('weekly', 'weekly')])),
                ('day_of_month', models.SmallIntegerField(blank=True, help_text='The day of the month to send the report. This field is required and only valid when the frequency is monthly.', null=True, verbose_name='Day of Month', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(31)])),
                ('day_of_week', models.SmallIntegerField(blank=True, help_text='The day of the week to send the report. This field is required and only valid when the frequency is weekly.', null=True, verbose_name='Day of Week', choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('hour_of_day', models.SmallIntegerField(help_text='The hour of the day to send the report, in Eastern Standard Time (EST). This is required for all frequency settings.', verbose_name='Hour of Day', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(23)])),
                ('initialization_vector', models.BinaryField(help_text='This is the initialization vector used to encrypt the password using AESencr', verbose_name='Password Encryption Initialization Vector', max_length=32)),
                ('password', models.BinaryField(verbose_name='Password', max_length=256)),
                ('enterprise_customer', models.OneToOneField(verbose_name='Enterprise Customer', to='enterprise.EnterpriseCustomer', on_delete=models.CASCADE)),
            ],
        ),
    ]
