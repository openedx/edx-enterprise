# Generated by Django 2.2.19 on 2022-05-17 16:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0157_make_field_nullable_before_removal'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalsystemwideenterpriseuserroleassignment',
            name='is_active',
        ),
        migrations.RemoveField(
            model_name='systemwideenterpriseuserroleassignment',
            name='is_active',
        ),
    ]
