# Generated by Django 3.2.20 on 2023-08-08 09:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0005_auto_20230707_0755'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='historicaldatasharingconsent',
            options={'get_latest_by': ('history_date', 'history_id'), 'ordering': ('-history_date', '-history_id'), 'verbose_name': 'historical Data Sharing Consent Record', 'verbose_name_plural': 'historical Data Sharing Consent Records'},
        ),
    ]
