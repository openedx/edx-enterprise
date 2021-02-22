# Generated by Django 2.2.19 on 2021-02-22 22:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('canvas', '0006_canvaslearnerassessmentdatatransmissionaudit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='canvasenterprisecustomerconfiguration',
            name='canvas_account_id',
            field=models.BigIntegerField(help_text='Account number to use during api calls. Called account_id in canvas.  Required to create courses etc.', null=True, verbose_name='Canvas Account Number'),
        ),
        migrations.AlterField(
            model_name='historicalcanvasenterprisecustomerconfiguration',
            name='canvas_account_id',
            field=models.BigIntegerField(help_text='Account number to use during api calls. Called account_id in canvas.  Required to create courses etc.', null=True, verbose_name='Canvas Account Number'),
        ),
    ]
