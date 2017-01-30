# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0014_enrollmentnotificationemailtemplate_historicalenrollmentnotificationemailtemplate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomeruser',
            name='enterprise_customer',
            field=models.ForeignKey(to='enterprise.EnterpriseCustomer', related_name='enterprise_customer_users'),
        ),
        migrations.AlterField(
            model_name='userdatasharingconsentaudit',
            name='user',
            field=models.ForeignKey(to='enterprise.EnterpriseCustomerUser', related_name='data_sharing_consent'),
        ),
    ]
