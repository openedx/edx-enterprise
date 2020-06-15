# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0018_auto_20170511_1357'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomer',
            name='require_account_level_consent',
            field=models.BooleanField(default=False, help_text='Specifies whether every consent interaction should ask for account-wide consent, rather than only the specific scope at which the interaction is happening.'),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomer',
            name='require_account_level_consent',
            field=models.BooleanField(default=False, help_text='Specifies whether every consent interaction should ask for account-wide consent, rather than only the specific scope at which the interaction is happening.'),
        ),
    ]
