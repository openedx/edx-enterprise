# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0034_auto_20171023_0727'),
    ]

    operations = [
        migrations.AddField(
            model_name='enterprisecustomercatalog',
            name='publish_audit_enrollment_urls',
            field=models.BooleanField(default=False, help_text='Specifies whether courses should be published with direct-to-audit enrollment URLs.'),
        ),
        migrations.AddField(
            model_name='historicalenterprisecustomercatalog',
            name='publish_audit_enrollment_urls',
            field=models.BooleanField(default=False, help_text='Specifies whether courses should be published with direct-to-audit enrollment URLs.'),
        ),
    ]
