from django.db import migrations

ADDITIONAL_ENTERPRISE_ENROLLMENT_SOURCES = {
    'Customer Admin Enrollment': 'customer_admin'
}

def add_new_enterprise_enrollment_source(apps, schema_editor):
    enrollment_sources = apps.get_model('enterprise', 'EnterpriseEnrollmentSource')
    for name, slug in ADDITIONAL_ENTERPRISE_ENROLLMENT_SOURCES.items():
        enrollment_sources.objects.update_or_create(name=name, slug=slug)


def drop_new_enterprise_enrollment_source(apps, schema_editor):
    enrollment_sources = apps.get_model('enterprise', 'EnterpriseEnrollmentSource')
    enrollment_sources.objects.filter(name__in=ADDITIONAL_ENTERPRISE_ENROLLMENT_SOURCES).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0139_auto_20210803_1854'),
    ]

    operations = [
        migrations.RunPython(
            code=add_new_enterprise_enrollment_source, reverse_code=drop_new_enterprise_enrollment_source
        )

    ]
