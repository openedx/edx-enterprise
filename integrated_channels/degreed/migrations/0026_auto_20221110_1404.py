# Generated by Django 3.2.16 on 2022-11-10 14:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0025_auto_20221031_1855'),
    ]

    operations = [
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='last_content_sync_attempted_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of attempted content transmission with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='last_content_sync_errored_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of a content transmission error with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='last_learner_sync_attempted_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of attempted learner transmission with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='last_learner_sync_errored_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of a learner transmission error with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='last_sync_attemped_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of attempted communication with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='degreedenterprisecustomerconfiguration',
            name='last_sync_errored_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of an error in communication with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='last_content_sync_attempted_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of attempted content transmission with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='last_content_sync_errored_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of a content transmission error with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='last_learner_sync_attempted_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of attempted learner transmission with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='last_learner_sync_errored_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of a learner transmission error with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='last_sync_attemped_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of attempted communication with this integrated channel.', null=True),
        ),
        migrations.AddField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='last_sync_errored_at',
            field=models.DateTimeField(blank=True, help_text='The last recorded time of an error in communication with this integrated channel.', null=True),
        ),
    ]
