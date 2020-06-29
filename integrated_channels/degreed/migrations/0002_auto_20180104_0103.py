# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='active',
            field=models.BooleanField(help_text='Is this configuration active ?'),
        ),
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='enterprise_customer',
            field=models.OneToOneField(help_text='Enterprise Customer associated with the configuration.', to='enterprise.EnterpriseCustomer', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='active',
            field=models.BooleanField(help_text='Is this configuration active ?'),
        ),
    ]
