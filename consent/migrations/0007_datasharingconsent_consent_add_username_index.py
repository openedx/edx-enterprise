# Generated by Django 4.2.15 on 2024-10-07 14:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0006_alter_historicaldatasharingconsent_options'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='datasharingconsent',
            index=models.Index(fields=['username'], name='consent_dat_usernam_fae23a_idx'),
        ),
    ]
