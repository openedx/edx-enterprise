# Generated by Django 3.2.12 on 2022-03-24 15:50

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0003_alter_sapsuccessfactorslearnerdatatransmissionaudit_completed_timestamp'),
    ]

    operations = [
        migrations.AddField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='enterprise_customer_uuid',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='modified',
            field=model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified'),
        ),
        migrations.AddField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='plugin_configuration_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='created',
            field=model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created'),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='enterprise_course_enrollment_id',
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='error_message',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorslearnerdatatransmissionaudit',
            name='status',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
