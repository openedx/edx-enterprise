# Generated by Django 2.2.16 on 2020-10-09 16:47

import django.db.models.deletion
from django.db import migrations, models

import enterprise.models
import enterprise.validators


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0113_auto_20200914_2054'),
    ]

    operations = [
        migrations.RenameField(
            model_name='enterprisecustomerbrandingconfiguration',
            old_name='logo',
            new_name='_logo',
        ),
        migrations.AlterField(
            model_name='enterprisecustomerbrandingconfiguration',
            name='_logo',
            field=models.ImageField(blank=True, db_column='logo', help_text='Logo images must be in .png format.', max_length=255, null=True, upload_to=enterprise.models.logo_path, validators=[enterprise.validators.validate_image_extension, enterprise.validators.validate_image_size]),
        ),
        migrations.AlterField(
            model_name='enterprisecustomerbrandingconfiguration',
            name='enterprise_customer',
            field=models.OneToOneField(db_column='branding_configuration', on_delete=django.db.models.deletion.CASCADE, related_name='_branding_configuration', to='enterprise.EnterpriseCustomer'),
        ),
    ]
