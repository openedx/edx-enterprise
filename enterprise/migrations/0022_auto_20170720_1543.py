# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0021_auto_20170711_0712'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomer',
            name='enforce_data_sharing_consent',
            field=models.CharField(default='at_enrollment', help_text='Specifies whether data sharing consent is optional, is required at login, or is required at enrollment.', max_length=25, choices=[('at_enrollment', 'At Enrollment'), ('externally_managed', 'Managed externally')]),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomer',
            name='enforce_data_sharing_consent',
            field=models.CharField(default='at_enrollment', help_text='Specifies whether data sharing consent is optional, is required at login, or is required at enrollment.', max_length=25, choices=[('at_enrollment', 'At Enrollment'), ('externally_managed', 'Managed externally')]),
        ),
    ]
