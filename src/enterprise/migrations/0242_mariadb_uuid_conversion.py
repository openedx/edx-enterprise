# Generated migration for MariaDB UUID field conversion (Django 5.2)
"""
Migration to convert UUIDField from char(32) to uuid type for MariaDB compatibility.

See: https://www.albertyw.com/note/django-5-mariadb-uuidfield
"""

from django.db import migrations


def apply_mariadb_migration(apps, schema_editor):
    connection = schema_editor.connection
    
    if connection.vendor != 'mysql':
        return
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        if 'mariadb' not in version.lower():
            return
    
    with connection.cursor() as cursor:
        # EnterpriseCustomer
        cursor.execute("ALTER TABLE enterprise_enterprisecustomer MODIFY uuid uuid NOT NULL")
        
        # PendingEnrollment
        cursor.execute("ALTER TABLE enterprise_pendingenrollment MODIFY license_uuid uuid NULL")
        cursor.execute("ALTER TABLE enterprise_historicalpendingenrollment MODIFY license_uuid uuid NULL")
        
        # EnterpriseCourseEntitlement
        cursor.execute("ALTER TABLE enterprise_enterprisecourseentitlement MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_historicalenterprisecourseentitlement MODIFY uuid uuid NOT NULL")
        
        # Other enterprise models with UUIDs
        cursor.execute("ALTER TABLE enterprise_learnercreditenterprisecourseenrollment MODIFY transaction_id uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_licensedenterprisecourseenrollment MODIFY license_uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_defaultenterpriseenrollmentintention MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecatalogquery MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomercatalog MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomerreportingconfiguration MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomerinvitekey MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_historicalenterprisecustomerinvitekey MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_chatgptresponse MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomerssoconfiguration MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisegroup MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_historicalenterprisegroup MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisegroupmembership MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_onboardingflow MODIFY uuid uuid NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomeradmin MODIFY uuid uuid NOT NULL")


def reverse_mariadb_migration(apps, schema_editor):
    connection = schema_editor.connection
    
    if connection.vendor != 'mysql':
        return
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        if 'mariadb' not in version.lower():
            return
    
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE enterprise_enterprisecustomer MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_pendingenrollment MODIFY license_uuid char(32) NULL")
        cursor.execute("ALTER TABLE enterprise_historicalpendingenrollment MODIFY license_uuid char(32) NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecourseentitlement MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_historicalenterprisecourseentitlement MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_learnercreditenterprisecourseenrollment MODIFY transaction_id char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_licensedenterprisecourseenrollment MODIFY license_uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_defaultenterpriseenrollmentintention MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecatalogquery MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomercatalog MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomerreportingconfiguration MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomerinvitekey MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_historicalenterprisecustomerinvitekey MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_chatgptresponse MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomerssoconfiguration MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisegroup MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_historicalenterprisegroup MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisegroupmembership MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_onboardingflow MODIFY uuid char(32) NOT NULL")
        cursor.execute("ALTER TABLE enterprise_enterprisecustomeradmin MODIFY uuid char(32) NOT NULL")


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0241_alter_defaultenterpriseenrollmentintention_realized_enrollments'),
    ]

    operations = [
        migrations.RunPython(
            code=apply_mariadb_migration,
            reverse_code=reverse_mariadb_migration,
        ),
    ]
