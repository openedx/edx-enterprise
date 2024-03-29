# Generated by Django 2.2.24 on 2021-09-30 21:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cornerstone', '0009_auto_20210923_1727'),
    ]

    operations = [
        migrations.CreateModel(
            name='CornerstoneCourseKey',
            fields=[
                ('internal_course_id', models.CharField(help_text='This is the edX course key that is used as a unique identifier.', max_length=255, primary_key=True, serialize=False)),
                ('external_course_id', models.CharField(help_text='This is the course key that is being sent to our partners.', max_length=255)),
            ],
        ),
    ]
