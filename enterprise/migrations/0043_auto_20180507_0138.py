# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0042_replace_sensitive_sso_username'),
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
            options={'verbose_name': 'Enterprise Customer', 'verbose_name_plural': 'Enterprise Customers', 'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomerbrandingconfiguration',
            options={'verbose_name': 'Branding Configuration', 'verbose_name_plural': 'Branding Configurations', 'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomercatalog',
            options={'verbose_name': 'Enterprise Customer Catalog', 'verbose_name_plural': 'Enterprise Customer Catalogs', 'ordering': ['created']},
        ),
        migrations.AlterModelOptions(
            name='enterprisecustomerentitlement',
            options={'verbose_name': 'Enterprise Customer Entitlement', 'verbose_name_plural': 'Enterprise Customer Entitlements', 'ordering': ['created']},
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
            options={'verbose_name': 'Enterprise Customer Learner', 'verbose_name_plural': 'Enterprise Customer Learners', 'ordering': ['created']},
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
