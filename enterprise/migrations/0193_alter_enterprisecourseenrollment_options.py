# Generated by Django 4.2 on 2023-12-29 17:03

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0192_auto_20231009_1302'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='enterprisecourseenrollment',
            options={'ordering': ['id']},
        ),
    ]
