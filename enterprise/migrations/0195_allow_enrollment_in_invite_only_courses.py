# Generated by Django 3.2.23 on 2023-12-08 09:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0194_hide_course_price_when_zero'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomer',
            name='allow_enrollment_in_invite_only_courses',
            field=models.BooleanField(default=False, help_text="Specifies if learners are allowed to enroll into courses marked as 'invitation-only', when they attempt to enroll from the landing page."),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='allow_enrollment_in_invite_only_courses',
            field=models.BooleanField(default=False, help_text="Specifies if learners are allowed to enroll into courses marked as 'invitation-only', when they attempt to enroll from the landing page."),
        ),
    ]
