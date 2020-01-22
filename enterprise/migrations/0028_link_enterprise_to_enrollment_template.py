# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0027_remove_account_level_consent'),
    ]

    operations = [
        migrations.AddField(
            model_name='enrollmentnotificationemailtemplate',
            name='enterprise_customer',
            field=models.OneToOneField(related_name='enterprise_enrollment_template', default=None, to='enterprise.EnterpriseCustomer', on_delete=models.CASCADE),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicalenrollmentnotificationemailtemplate',
            name='enterprise_customer',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='enterprise.EnterpriseCustomer', null=True),
        ),
        migrations.AlterField(
            model_name='enrollmentnotificationemailtemplate',
            name='site',
            field=models.OneToOneField(related_name='enterprise_enrollment_template', null=True, blank=True, to='sites.Site', on_delete=models.CASCADE),
        ),
]
