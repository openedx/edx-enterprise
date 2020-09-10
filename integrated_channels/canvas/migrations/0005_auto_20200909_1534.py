# Generated by Django 2.2.15 on 2020-09-09 15:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('canvas', '0004_adding_learner_data_to_canvas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='canvaslearnerdatatransmissionaudit',
            name='completed_timestamp',
            field=models.CharField(help_text='Represents the canvas representation of a timestamp: yyyy-mm-dd, which is always 10 characters.', max_length=10),
        ),
        migrations.AlterField(
            model_name='canvaslearnerdatatransmissionaudit',
            name='course_completed',
            field=models.BooleanField(default=False, help_text="The learner's course completion status transmitted to Canvas."),
        ),
    ]
