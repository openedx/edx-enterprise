from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0002_migrate_to_new_data_sharing_consent'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicaldatasharingconsent',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
