# Generated by Django 3.2.12 on 2022-03-24 19:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cornerstone', '0016_auto_20220324_1550'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cornerstonelearnerdatatransmissionaudit',
            name='course_completed',
            field=models.BooleanField(default=False),
        ),
    ]
