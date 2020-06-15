# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0006_sapsuccessfactors_use_enterprise_enrollment_page_waffle_flag'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='history_change_reason',
        ),
    ]
