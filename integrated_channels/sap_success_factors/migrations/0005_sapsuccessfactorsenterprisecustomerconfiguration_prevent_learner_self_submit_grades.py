# Generated by Django 2.2.24 on 2021-07-16 18:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0004_auto_20210708_1639'),
    ]

    operations = [
        migrations.AddField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='prevent_self_submit_grades',
            field=models.BooleanField(default=False, help_text="When set to True, the integration will use the generic edX service user ('sapsf_user_id') defined in the SAP Customer Configuration for course completion.", verbose_name='Prevent Learner From Self-Submitting Grades'),
        ),
    ]
