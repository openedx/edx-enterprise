# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0043_reporting_config_multiple_types'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='enrollmentnotificationemailtemplate',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='enterprisecourseenrollment',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomer',
            options={'ordering': ['created'], 'verbose_name': 'Enterprise Customer', 'verbose_name_plural': 'Enterprise Customers'},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomerbrandingconfiguration',
            options={'ordering': ['created'], 'verbose_name': 'Branding Configuration', 'verbose_name_plural': 'Branding Configurations'},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomercatalog',
            options={'ordering': ['created'], 'verbose_name': 'Enterprise Customer Catalog', 'verbose_name_plural': 'Enterprise Customer Catalogs'},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomerentitlement',
            options={'ordering': ['created'], 'verbose_name': 'Enterprise Customer Entitlement', 'verbose_name_plural': 'Enterprise Customer Entitlements'},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomeridentityprovider',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomerreportingconfiguration',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomeruser',
            options={'ordering': ['created'], 'verbose_name': 'Enterprise Customer Learner', 'verbose_name_plural': 'Enterprise Customer Learners'},
        ),
        migrations.AlterModelOptions(
            name='pendingenrollment',
            options={'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='pendingenterprisecustomeruser',
            options={'ordering': ['created']},
        ),
    ]
