# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0011_auto_20180104_0103'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalsapsuccessfactorsenterprisecustomerconfiguration',
            name='active',
            field=models.BooleanField(help_text='Is this configuration active?'),
        ),
        migrations.AlterField(
            model_name='sapsuccessfactorsenterprisecustomerconfiguration',
            name='active',
            field=models.BooleanField(help_text='Is this configuration active?'),
        ),
    ]
