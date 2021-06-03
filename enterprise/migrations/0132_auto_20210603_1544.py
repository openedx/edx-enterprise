# Generated by Django 2.2.20 on 2021-06-03 15:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0131_auto_20210517_0924'),
    ]

    operations = [
        migrations.AddField(
            model_name='enrollmentnotificationemailtemplate',
            name='template_type',
            field=models.CharField(choices=[('DE', 'Default Enrollment Template'), ('BE', 'Bulk Enrollment Template')], default='DE', help_text='Use either DE (default) or BE (bulk enrollment)', max_length=2),
        ),
        migrations.AddField(
            model_name='historicalenrollmentnotificationemailtemplate',
            name='template_type',
            field=models.CharField(choices=[('DE', 'Default Enrollment Template'), ('BE', 'Bulk Enrollment Template')], default='DE', help_text='Use either DE (default) or BE (bulk enrollment)', max_length=2),
        ),
        migrations.AlterField(
            model_name='enrollmentnotificationemailtemplate',
            name='enterprise_customer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enterprise_enrollment_templates', to='enterprise.EnterpriseCustomer'),
        ),
    ]
