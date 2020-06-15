# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0014_drop_historical_table'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='enterprise_customer',
        ),
        migrations.RemoveField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='history_user',
        ),
        migrations.DeleteModel(
            name='HistoricalSAPSuccessFactorsEnterpriseCustomerConfiguration',
        ),
    ]
