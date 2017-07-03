# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enterprise', '0013_auto_20170125_1157'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnrollmentNotificationEmailTemplate',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('plaintext_template', models.TextField(help_text='Fill in a standard Django template that, when rendered, produces the email you want sent to newly-enrolled Enterprise Customer users. The following variables may be available:\n<ul><li>user_name: A human-readable name for the person being emailed. Be sure to handle the case where this is not defined, as it may be missing in some cases. It may also be a username, if the user hasn\'t configured their "real" name in the system.</li>    <li>organization_name: The name of the organization sponsoring the enrollment.</li>    <li>enrolled_in: Details of the course or program that was enrolled in. Possible items it contains:    <ul><li>name: The name of the enrollable item (e.g., "Demo Course").</li>        <li>url: A link to the homepage of the enrolled-in item.</li>        <li>branding: A custom branding name for the enrolled-in item. For example, the branding of a MicroMasters program would be "MicroMasters".</li>     <li>start: The date the enrolled-in item becomes available. Render this to text using the Django `date` template filter (see <a href="https://docs.djangoproject.com/en/1.8/ref/templates/builtins/#date">the Django documentation</a>).</li><li>type: Whether the enrolled-in item is a course, a program, or something else.</li></ul></ul>', blank=True)),
                ('html_template', models.TextField(help_text='Fill in a standard Django template that, when rendered, produces the email you want sent to newly-enrolled Enterprise Customer users. The following variables may be available:\n<ul><li>user_name: A human-readable name for the person being emailed. Be sure to handle the case where this is not defined, as it may be missing in some cases. It may also be a username, if the user hasn\'t configured their "real" name in the system.</li>    <li>organization_name: The name of the organization sponsoring the enrollment.</li>    <li>enrolled_in: Details of the course or program that was enrolled in. Possible items it contains:    <ul><li>name: The name of the enrollable item (e.g., "Demo Course").</li>        <li>url: A link to the homepage of the enrolled-in item.</li>        <li>branding: A custom branding name for the enrolled-in item. For example, the branding of a MicroMasters program would be "MicroMasters".</li>     <li>start: The date the enrolled-in item becomes available. Render this to text using the Django `date` template filter (see <a href="https://docs.djangoproject.com/en/1.8/ref/templates/builtins/#date">the Django documentation</a>).</li><li>type: Whether the enrolled-in item is a course, a program, or something else.</li></ul></ul>', blank=True)),
                ('subject_line', models.CharField(help_text='Fill in a string that can be used to generate a dynamic subject line for notification emails. The placeholder {course_name} will be replaced with the name of the course or program that was enrolled in.', max_length=100, blank=True)),
                ('site', models.OneToOneField(related_name='enterprise_enrollment_template', on_delete=django.db.models.deletion.CASCADE, to='sites.Site')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalEnrollmentNotificationEmailTemplate',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('plaintext_template', models.TextField(help_text='Fill in a standard Django template that, when rendered, produces the email you want sent to newly-enrolled Enterprise Customer users. The following variables may be available:\n<ul><li>user_name: A human-readable name for the person being emailed. Be sure to handle the case where this is not defined, as it may be missing in some cases. It may also be a username, if the user hasn\'t configured their "real" name in the system.</li>    <li>organization_name: The name of the organization sponsoring the enrollment.</li>    <li>enrolled_in: Details of the course or program that was enrolled in. Possible items it contains:    <ul><li>name: The name of the enrollable item (e.g., "Demo Course").</li>        <li>url: A link to the homepage of the enrolled-in item.</li>        <li>branding: A custom branding name for the enrolled-in item. For example, the branding of a MicroMasters program would be "MicroMasters".</li>     <li>start: The date the enrolled-in item becomes available. Render this to text using the Django `date` template filter (see <a href="https://docs.djangoproject.com/en/1.8/ref/templates/builtins/#date">the Django documentation</a>).</li><li>type: Whether the enrolled-in item is a course, a program, or something else.</li></ul></ul>', blank=True)),
                ('html_template', models.TextField(help_text='Fill in a standard Django template that, when rendered, produces the email you want sent to newly-enrolled Enterprise Customer users. The following variables may be available:\n<ul><li>user_name: A human-readable name for the person being emailed. Be sure to handle the case where this is not defined, as it may be missing in some cases. It may also be a username, if the user hasn\'t configured their "real" name in the system.</li>    <li>organization_name: The name of the organization sponsoring the enrollment.</li>    <li>enrolled_in: Details of the course or program that was enrolled in. Possible items it contains:    <ul><li>name: The name of the enrollable item (e.g., "Demo Course").</li>        <li>url: A link to the homepage of the enrolled-in item.</li>        <li>branding: A custom branding name for the enrolled-in item. For example, the branding of a MicroMasters program would be "MicroMasters".</li>     <li>start: The date the enrolled-in item becomes available. Render this to text using the Django `date` template filter (see <a href="https://docs.djangoproject.com/en/1.8/ref/templates/builtins/#date">the Django documentation</a>).</li><li>type: Whether the enrolled-in item is a course, a program, or something else.</li></ul></ul>', blank=True)),
                ('subject_line', models.CharField(help_text='Fill in a string that can be used to generate a dynamic subject line for notification emails. The placeholder {course_name} will be replaced with the name of the course or program that was enrolled in.', max_length=100, blank=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('site', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='sites.Site', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical enrollment notification email template',
            },
        ),
    ]
