# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrated_channel', '0003_catalogtransmissionaudit_learnerdatatransmissionaudit'),
    ]

    operations = [
        migrations.AddField(
            model_name='catalogtransmissionaudit',
            name='channel',
            field=models.CharField(default='SAP', max_length=30),
            preserve_default=False,
        ),
    ]
