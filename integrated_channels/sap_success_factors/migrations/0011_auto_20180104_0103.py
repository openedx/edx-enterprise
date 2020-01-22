# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0010_move_audit_tables_to_base_integrated_channel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='active',
            field=models.BooleanField(help_text='Is this configuration active ?'),
        ),
        migrations.AlterField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='key',
            field=models.CharField(help_text='OAuth client identifier.', verbose_name='Client ID', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='sapsf_base_url',
            field=models.CharField(help_text='Base URL of success factors API.', verbose_name='SAP Base URL', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='sapsf_company_id',
            field=models.CharField(help_text='Success factors company identifier.', verbose_name='SAP Company ID', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='sapsf_user_id',
            field=models.CharField(help_text='Success factors user identifier.', verbose_name='SAP User ID', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='secret',
            field=models.CharField(help_text='OAuth client secret.', verbose_name='Client Secret', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='user_type',
            field=models.CharField(help_text='Type of SAP User (admin or user).', default='user', choices=[('user', 'User'), ('admin', 'Admin')], verbose_name='SAP User Type', max_length=20),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='active',
            field=models.BooleanField(help_text='Is this configuration active ?'),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='enterprise_customer',
            field=models.OneToOneField(help_text='Enterprise Customer associated with the configuration.', to='enterprise.EnterpriseCustomer', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='key',
            field=models.CharField(help_text='OAuth client identifier.', verbose_name='Client ID', max_length=255),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='sapsf_base_url',
            field=models.CharField(help_text='Base URL of success factors API.', verbose_name='SAP Base URL', max_length=255),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='sapsf_company_id',
            field=models.CharField(help_text='Success factors company identifier.', verbose_name='SAP Company ID', max_length=255),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='sapsf_user_id',
            field=models.CharField(help_text='Success factors user identifier.', verbose_name='SAP User ID', max_length=255),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='secret',
            field=models.CharField(help_text='OAuth client secret.', verbose_name='Client Secret', max_length=255),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='user_type',
            field=models.CharField(help_text='Type of SAP User (admin or user).', default='user', choices=[('user', 'User'), ('admin', 'Admin')], verbose_name='SAP User Type', max_length=20),
        ),
    ]
