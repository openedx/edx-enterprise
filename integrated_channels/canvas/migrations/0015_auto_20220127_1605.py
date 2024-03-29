# Generated by Django 3.2.11 on 2022-01-27 16:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('canvas', '0014_auto_20220126_1837'),
    ]

    operations = [
        migrations.AlterField(
            model_name='canvasenterprisecustomerconfiguration',
            name='canvas_account_id',
            field=models.BigIntegerField(blank=True, help_text='Account number to use during api calls. Called account_id in canvas.  Required to create courses etc.', null=True, verbose_name='Canvas Account Number'),
        ),
        migrations.AlterField(
            model_name='historicalcanvasenterprisecustomerconfiguration',
            name='canvas_account_id',
            field=models.BigIntegerField(blank=True, help_text='Account number to use during api calls. Called account_id in canvas.  Required to create courses etc.', null=True, verbose_name='Canvas Account Number'),
        ),
    ]
