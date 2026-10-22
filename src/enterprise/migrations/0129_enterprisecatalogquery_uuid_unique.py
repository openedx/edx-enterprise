from django.db import migrations, models
import uuid

class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0128_enterprisecatalogquery_generate_uuids'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecatalogquery',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, blank=False, null=False, unique=True),
        ),
    ]
