"""
Python API for various enterprise functionality.
"""
from django.utils import timezone

from enterprise import roles_api
from enterprise.models import EnterpriseCustomerAdmin, PendingEnterpriseCustomerAdminUser


def activate_admin_permissions(enterprise_customer_user):
    """
    Activates admin permissions for an existing PendingEnterpriseCustomerAdminUser.

    Specifically, the "enterprise_admin" system-wide role is assigned to the user and
    the PendingEnterpriseCustomerAdminUser record is removed.

    Requires an EnterpriseCustomerUser record to exist which ensures the user already
    has the "enterprise_learner" role as a prerequisite.

    Arguments:
        enterprise_customer_user: an EnterpriseCustomerUser instance
    """
    try:
        pending_admin_user = PendingEnterpriseCustomerAdminUser.objects.get(
            user_email=enterprise_customer_user.user.email,
            enterprise_customer=enterprise_customer_user.enterprise_customer,
        )
        # if this user is an admin, we want to create an accompanying EnterpriseCustomerAdmin record
        # with the invited_date from the pending record and joined_date set to now
        admin_record, created = EnterpriseCustomerAdmin.objects.get_or_create(
            enterprise_customer_user=enterprise_customer_user,
            defaults={
                'invited_date': pending_admin_user.created,
                'joined_date': timezone.now(),
            }
        )
        
        # If the record already exists but joined_date is null, update it
        if not created and not admin_record.joined_date:
            admin_record.joined_date = timezone.now()
            admin_record.save(update_fields=['joined_date'])
            
    except PendingEnterpriseCustomerAdminUser.DoesNotExist:
        return  # this is ok, nothing to do

    if not enterprise_customer_user.linked:
        # EnterpriseCustomerUser is no longer linked, so delete the "enterprise_admin" role.
        # TODO: ENT-3914 | Add `enterprise_customer=enterprise_customer_user.enterprise_customer`
        # kwarg so that we delete at most a single assignment instance.
        roles_api.delete_admin_role_assignment(
            enterprise_customer_user.user,
        )
        return  # nothing left to do

    roles_api.assign_admin_role(
        enterprise_customer_user.user,
        enterprise_customer=enterprise_customer_user.enterprise_customer
    )

    # delete the PendingEnterpriseCustomerAdminUser record
    pending_admin_user.delete()
