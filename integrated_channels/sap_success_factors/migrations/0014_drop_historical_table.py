# -*- coding: utf-8 -*-


from django.db import connection, migrations


def dropHistoricalTable(apps, schema_editor):
    """
    Drops the historical sap_success_factors table named herein.
    """
    table_name = 'sap_success_factors_historicalsapsuccessfactorsenterprisecus80ad'
    if table_name in connection.introspection.table_names():
        migrations.DeleteModel(
            name=table_name,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0013_auto_20180306_1251'),
    ]

    operations = [
        migrations.RunPython(dropHistoricalTable),
    ]
