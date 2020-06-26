# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0028_link_enterprise_to_enrollment_template'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomercatalog',
            name='enterprise_customer',
            field=models.ForeignKey(related_name='enterprise_customer_catalogs', to='enterprise.EnterpriseCustomer', on_delete=models.CASCADE),
        ),
    ]
