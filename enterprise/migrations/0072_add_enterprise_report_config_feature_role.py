# -*- coding: utf-8 -*-


from django.db import migrations

from enterprise.constants import ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE


def create_roles(apps, schema_editor):
    """Create the enterprise roles if they do not already exist."""
    EnterpriseFeatureRole = apps.get_model('enterprise', 'EnterpriseFeatureRole')
    EnterpriseFeatureRole.objects.update_or_create(name=ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE)


def delete_roles(apps, schema_editor):
    """Delete the enterprise roles."""
    EnterpriseFeatureRole = apps.get_model('enterprise', 'EnterpriseFeatureRole')
    EnterpriseFeatureRole.objects.filter(
        name__in=[ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0065_add_enterprise_feature_roles'),
        ('enterprise', '0071_historicalpendingenrollment_historicalpendingenterprisecustomeruser'),
    ]

    operations = [
        migrations.RunPython(create_roles, delete_roles)
    ]
