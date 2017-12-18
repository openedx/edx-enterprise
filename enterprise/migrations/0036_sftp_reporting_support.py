# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0035_auto_20171212_1129'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomerreportingconfiguration',
            name='sftp_file_path',
            field=models.CharField(help_text='If the delivery method is sftp, the path on the host to deliver the report to.', max_length=256, null=True, verbose_name='SFTP file path', blank=True),
        ),
        migrations.AddField(
            model_name='enterprisecustomerreportingconfiguration',
            name='sftp_hostname',
            field=models.CharField(help_text='If the delivery method is sftp, the host to deliver the report to.', max_length=256, null=True, verbose_name='SFTP Host name', blank=True),
        ),
        migrations.AddField(
            model_name='enterprisecustomerreportingconfiguration',
            name='sftp_password',
            field=models.BinaryField(max_length=256, blank=True, help_text='If the delivery method is sftp, the password to use to securely access the host.', null=True, verbose_name='SFTP password'),
        ),
        migrations.AddField(
            model_name='enterprisecustomerreportingconfiguration',
            name='sftp_port',
            field=models.PositiveIntegerField(default=22, help_text='If the delivery method is sftp, the port on the host to connect to.', null=True, verbose_name='SFTP Port', blank=True),
        ),
        migrations.AddField(
            model_name='enterprisecustomerreportingconfiguration',
            name='sftp_username',
            field=models.CharField(help_text='If the delivery method is sftp, the username to use to securely access the host.', max_length=256, null=True, verbose_name='SFTP username', blank=True),
        ),
        migrations.AlterField(
            model_name='enterprisecustomerreportingconfiguration',
            name='delivery_method',
            field=models.CharField(default='email', help_text='The method in which the data should be sent.', max_length=20, verbose_name='Delivery Method', choices=[('email', 'email'), ('sftp', 'sftp')]),
        ),
        migrations.AlterField(
            model_name='enterprisecustomerreportingconfiguration',
            name='password',
            field=models.BinaryField(verbose_name='Password for the protected zip file.', max_length=256),
        ),
    ]
