from django.db import migrations
import uuid

def generate_uuid(apps, schema_editor):
    EnterpriseCatalogQuery = apps.get_model('enterprise', 'EnterpriseCatalogQuery')
    for row in EnterpriseCatalogQuery.objects.all():
        row.uuid = uuid.uuid4()
        row.save(update_fields=['uuid'])

class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0127_enterprisecatalogquery_uuid'),
    ]

    operations = [
        migrations.RunPython(generate_uuid, reverse_code=migrations.RunPython.noop),
    ]
