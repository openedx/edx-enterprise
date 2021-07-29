# Generated by Django 2.2.20 on 2021-06-10 08:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0133_auto_20210608_1931'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomerreportingconfiguration',
            name='enable_compression',
            field=models.BooleanField(default=True, help_text='Specifies whether report should be compressed. Without compression files will not be password protected or encrypted.'),
        ),
    ]
