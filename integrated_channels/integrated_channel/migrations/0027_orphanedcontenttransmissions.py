# Generated by Django 3.2.18 on 2023-03-31 18:14

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('integrated_channel', '0026_genericenterprisecustomerpluginconfiguration_last_modified_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrphanedContentTransmissions',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('integrated_channel_code', models.CharField(max_length=30)),
                ('plugin_configuration_id', models.PositiveIntegerField()),
                ('content_id', models.CharField(max_length=255)),
                ('resolved', models.BooleanField(default=False)),
                ('transmission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orphaned_record', to='integrated_channel.contentmetadataitemtransmission')),
            ],
            options={
                'index_together': {('integrated_channel_code', 'plugin_configuration_id', 'resolved')},
            },
        ),
    ]
