# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0025_auto_20170828_1412'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomer',
            name='require_account_level_consent',
            field=models.NullBooleanField(default=False, help_text='Specifies whether every consent interaction should ask for account-wide consent, rather than only the specific scope at which the interaction is happening.'),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomer',
            name='require_account_level_consent',
            field=models.NullBooleanField(default=False, help_text='Specifies whether every consent interaction should ask for account-wide consent, rather than only the specific scope at which the interaction is happening.'),
        ),
    ]
