# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from enterprise.constants import (
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
)


def create_roles(apps, schema_editor):
    """Create the enterprise roles if they do not already exist."""
    EnterpriseFeatureRole = apps.get_model('enterprise', 'EnterpriseFeatureRole')
    EnterpriseFeatureRole.objects.update_or_create(name=ENTERPRISE_CATALOG_ADMIN_ROLE)
    EnterpriseFeatureRole.objects.update_or_create(name=ENTERPRISE_DASHBOARD_ADMIN_ROLE)
    EnterpriseFeatureRole.objects.update_or_create(name=ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE)


def delete_roles(apps, schema_editor):
    """Delete the enterprise roles."""
    EnterpriseFeatureRole = apps.get_model('enterprise', 'EnterpriseFeatureRole')
    EnterpriseFeatureRole.objects.filter(
        name__in=[ENTERPRISE_CATALOG_ADMIN_ROLE, ENTERPRISE_DASHBOARD_ADMIN_ROLE, ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0064_enterprisefeaturerole_enterprisefeatureuserroleassignment'),
    ]

    operations = [
        migrations.RunPython(create_roles, delete_roles)
    ]
