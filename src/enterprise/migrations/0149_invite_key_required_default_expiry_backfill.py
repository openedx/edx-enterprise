from django.db import migrations
from datetime import timedelta
    

def _bulk_update_expiration_date(cls, queryset):
    for invite_key in queryset:
        invite_key.expiration_date = invite_key.created + timedelta(days=365)
    cls.objects.bulk_update(queryset, ['expiration_date'])


def backfill_null_expiry_date_for_invite_keys(apps, schema_editor):
    """
    Finds all EnterpriseCustomerInviteKey objects with null expiration_date and applies a default
    expiration_date of 1-year from when the EnterpriseCustomerInviteKey object was created as a
    reasonable fallback such that there are no objects with expiration_date as null so a future
    migration can require this field at the Django admin and database levels.
    """
    EnterpriseCustomerInviteKey = apps.get_model('enterprise', 'EnterpriseCustomerInviteKey')
    HistoricalEnterpriseCustomerInviteKey = apps.get_model('enterprise', 'HistoricalEnterpriseCustomerInviteKey')
    queryset = EnterpriseCustomerInviteKey.objects.filter(expiration_date__isnull=True)
    history_queryset = HistoricalEnterpriseCustomerInviteKey.objects.filter(expiration_date__isnull=True)
    _bulk_update_expiration_date(cls=EnterpriseCustomerInviteKey, queryset=queryset)
    _bulk_update_expiration_date(cls=HistoricalEnterpriseCustomerInviteKey, queryset=history_queryset)

class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0148_auto_20211129_2114'),
    ]

    operations = [
        migrations.RunPython(
            code=backfill_null_expiry_date_for_invite_keys,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
