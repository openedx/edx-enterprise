# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
        ('enterprise', '0002_enterprisecustomerbrandingconfiguration'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='enterprisecustomerbrandingconfiguration',
            options={'verbose_name': 'Branding Configuration', 'verbose_name_plural': 'Branding Configurations'},
        ),
        migrations.AddField(
            model_name='enterprisecustomer',
            name='site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enterprise_customers', default=1, to='sites.Site'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='site',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='sites.Site', null=True),
        ),
        migrations.AlterField(
            model_name='enterprisecustomerbrandingconfiguration',
            name='enterprise_customer',
            field=models.OneToOneField(related_name='branding_configuration', on_delete=django.db.models.deletion.CASCADE, to='enterprise.EnterpriseCustomer'),
        ),
    ]
