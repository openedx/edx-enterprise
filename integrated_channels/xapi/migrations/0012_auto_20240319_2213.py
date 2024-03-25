# Generated by Django 3.2.19 on 2024-03-19 22:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xapi', '0011_alter_xapilearnerdatatransmissionaudit_index_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='xapilearnerdatatransmissionaudit',
            name='enterprise_course_enrollment_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='xapilearnerdatatransmissionaudit',
            index=models.Index(fields=['error_message', 'enterprise_course_enrollment_id'], name='xapi_course_error_idx'),
        ),
    ]
