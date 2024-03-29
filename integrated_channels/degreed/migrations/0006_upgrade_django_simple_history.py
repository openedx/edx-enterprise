# Generated by Django 1.11.15 on 2018-12-13 15:23
# This is necessary because django-simple-history 2.6.0 changes the model


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0005_auto_20180807_1302'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='enterprise_customer',
            field=models.ForeignKey(blank=True, db_constraint=False, help_text='Enterprise Customer associated with the configuration.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='enterprise.EnterpriseCustomer'),
        ),
    ]
