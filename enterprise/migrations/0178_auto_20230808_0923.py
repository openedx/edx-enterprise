# Generated by Django 3.2.20 on 2023-08-08 09:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0177_auto_20230712_1925'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='historicalenrollmentnotificationemailtemplate',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical enrollment notification email template', 'verbose_name_plural': 'historical enrollment notification email templates'},
        ),
        migrations.AlterModelOptions(
            name='historicalenterprisecourseenrollment',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical enterprise course enrollment', 'verbose_name_plural': 'historical enterprise course enrollments'},
        ),
        migrations.AlterModelOptions(
            name='historicalenterprisecourseentitlement',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical enterprise course entitlement', 'verbose_name_plural': 'historical enterprise course entitlements'},
        ),
        migrations.AlterModelOptions(
            name='historicalenterprisecustomer',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical Enterprise Customer', 'verbose_name_plural': 'historical Enterprise Customers'},
        ),
        migrations.AlterModelOptions(
            name='historicalenterprisecustomercatalog',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical Enterprise Customer Catalog', 'verbose_name_plural': 'historical Enterprise Customer Catalogs'},
        ),
        migrations.AlterModelOptions(
            name='historicalenterprisecustomerinvitekey',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical enterprise customer invite key', 'verbose_name_plural': 'historical enterprise customer invite keys'},
        ),
        migrations.AlterModelOptions(
            name='historicalenterprisecustomeruser',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical Enterprise Customer Learner', 'verbose_name_plural': 'historical Enterprise Customer Learners'},
        ),
        migrations.AlterModelOptions(
            name='historicallearnercreditenterprisecourseenrollment',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical learner credit enterprise course enrollment', 'verbose_name_plural': 'historical learner credit enterprise course enrollments'},
        ),
        migrations.AlterModelOptions(
            name='historicallicensedenterprisecourseenrollment',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical licensed enterprise course enrollment', 'verbose_name_plural': 'historical licensed enterprise course enrollments'},
        ),
        migrations.AlterModelOptions(
            name='historicalpendingenrollment',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical pending enrollment', 'verbose_name_plural': 'historical pending enrollments'},
        ),
        migrations.AlterModelOptions(
            name='historicalpendingenterprisecustomeradminuser',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical pending enterprise customer admin user', 'verbose_name_plural': 'historical pending enterprise customer admin users'},
        ),
        migrations.AlterModelOptions(
            name='historicalpendingenterprisecustomeruser',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical pending enterprise customer user', 'verbose_name_plural': 'historical pending enterprise customer users'},
        ),
        migrations.AlterModelOptions(
            name='historicalsystemwideenterpriseuserroleassignment',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical system wide enterprise user role assignment', 'verbose_name_plural': 'historical system wide enterprise user role assignments'},
        ),
    ]
