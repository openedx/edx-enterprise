# Generated manually on 2026-02-08

from django.db import migrations


def backfill_admin_dates(apps, schema_editor):
    """
    Backfill invited_date and joined_date for existing EnterpriseCustomerAdmin records.
    
    Strategy:
    - Use the admin's created timestamp as invited_date (best approximation)
    - Use the same timestamp as joined_date (they're already active)
    - If last_login exists and is earlier than created, use it as joined_date
    """
    EnterpriseCustomerAdmin = apps.get_model('enterprise', 'EnterpriseCustomerAdmin')
    
    for admin in EnterpriseCustomerAdmin.objects.all():
        # Set invited_date to created timestamp if not already set
        if not admin.invited_date:
            admin.invited_date = admin.created
        
        # Set joined_date to created timestamp (or last_login if earlier)
        if not admin.joined_date:
            # If they have a last_login and it's earlier than created, use it
            if admin.last_login and admin.last_login < admin.created:
                admin.joined_date = admin.last_login
            else:
                admin.joined_date = admin.created
        
        admin.save(update_fields=['invited_date', 'joined_date'])


def reverse_backfill(apps, schema_editor):
    """
    Reverse migration - clear the backfilled data.
    """
    EnterpriseCustomerAdmin = apps.get_model('enterprise', 'EnterpriseCustomerAdmin')
    EnterpriseCustomerAdmin.objects.all().update(
        invited_date=None,
        joined_date=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0243_add_admin_invite_join_dates'),
    ]

    operations = [
        migrations.RunPython(
            backfill_admin_dates,
            reverse_backfill
        ),
    ]
