"""
Python API for various enterprise functionality.
"""
from enterprise import roles_api
from enterprise.models import PendingEnterpriseCustomerAdminUser


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
