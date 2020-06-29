# -*- coding: utf-8 -*-


from django.db import migrations

from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE


def create_roles(apps, schema_editor):
    """Create the enterprise roles if they do not already exist."""
    SystemWideEnterpriseRole = apps.get_model('enterprise', 'SystemWideEnterpriseRole')
    SystemWideEnterpriseRole.objects.update_or_create(name=ENTERPRISE_ADMIN_ROLE)
    SystemWideEnterpriseRole.objects.update_or_create(name=ENTERPRISE_LEARNER_ROLE)


def delete_roles(apps, schema_editor):
    """Delete the enterprise roles."""
    SystemWideEnterpriseRole = apps.get_model('enterprise', 'SystemWideEnterpriseRole')
    SystemWideEnterpriseRole.objects.filter(
        name__in=[ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0061_systemwideenterpriserole_systemwideenterpriseuserroleassignment'),
    ]

    operations = [
        migrations.RunPython(create_roles, delete_roles)
    ]
