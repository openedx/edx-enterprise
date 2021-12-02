from django.db import migrations
from dateutil.relativedelta import relativedelta
    

def backfill_null_expiry_date_for_invite_keys(apps, schema_editor):
    """
    Finds all EnterpriseCustomerInviteKey objects with null expiration_date and applies a default
    expiration_date of 1-year from when the EnterpriseCustomerInviteKey object was created as a
    reasonable such that there are no objects with expiration_date as null so a future migration
    can require this field at the Django admin and database levels.
    """
    EnterpriseCustomerInviteKey = apps.get_model('enterprise', 'EnterpriseCustomerInviteKey')
    queryset = EnterpriseCustomerInviteKey.objects.filter(expiration_date__isnull=True)
    for invite_key in queryset:
        invite_key.expiration_date = invite_key.created + relativedelta(years=1)
    EnterpriseCustomerInviteKey.objects.bulk_update(queryset, ['expiration_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0148_auto_20211129_2114'),
    ]

    operations = [
        migrations.RunPython(code=backfill_null_expiry_date_for_invite_keys, reverse_code=migrations.RunPython.noop),
    ]
