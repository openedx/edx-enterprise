"""
Create the ``Non-production`` enterprise customer type.

Assigning this customer type is what surfaces the non-production portal banner
(see ``EnterpriseCustomer.show_non_production_banner``), so it needs to exist out of the box.
"""

from django.db import migrations

from enterprise.constants import NON_PRODUCTION_CUSTOMER_TYPE


def create_non_production_customer_type(apps, schema_editor):  # pylint: disable=unused-argument
    """Create the `Non-production` enterprise customer type if it does not already exist."""
    EnterpriseCustomerType = apps.get_model('enterprise', 'EnterpriseCustomerType')
    EnterpriseCustomerType.objects.get_or_create(name=NON_PRODUCTION_CUSTOMER_TYPE)


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0250_alter_enterprisecustomer_customer_type_and_more'),
    ]

    operations = [
        # Reversing is intentionally a no-op: ``EnterpriseCustomer.customer_type`` cascades on
        # delete, so removing the customer type would delete any customer assigned to it.
        migrations.RunPython(
            code=create_non_production_customer_type,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
