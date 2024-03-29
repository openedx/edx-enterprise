# Generated by Django 3.2.20 on 2023-09-21 18:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0185_auto_20230921_1007'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomerssoconfiguration',
            name='entity_id',
            field=models.CharField(blank=True, help_text='The entity id of the identity provider.', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='enterprisecustomerssoconfiguration',
            name='metadata_url',
            field=models.CharField(blank=True, help_text='The metadata url of the identity provider.', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomerssoconfiguration',
            name='entity_id',
            field=models.CharField(blank=True, help_text='The entity id of the identity provider.', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomerssoconfiguration',
            name='metadata_url',
            field=models.CharField(blank=True, help_text='The metadata url of the identity provider.', max_length=255, null=True),
        ),
    ]
