"""
Python API for doing CRUD operations on roles and user role assignments.
"""
from cache_memoize import cache_memoize

from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE, ENTERPRISE_OPERATOR_ROLE
from enterprise.models import SystemWideEnterpriseRole, SystemWideEnterpriseUserRoleAssignment


# django-cache-memoize lets us explicitly declare a prefix
# to use as part of the cache key (rather than using the function name),
# which we're doing here just to be extra-careful about cache key collisions.
# https://github.com/peterbe/django-cache-memoize/blob/79c19f0314ff09d3f67d995f8d21f213e4eec3c8/src/cache_memoize/__init__.py#L99-L109
@cache_memoize(60 * 60, prefix='enterprise_system_wide_role')
def get_or_create_system_wide_role(role_name):
    """
    Gets or creates the `SystemWideEnterpriseRole` with the given name.
    Caches the result for 60 minutes in the Django cache.
    Returns the role object.
    """
    return SystemWideEnterpriseRole.objects.get_or_create(name=role_name)[0]


def admin_role():
    """ Return the enterprise admin role. """
    return get_or_create_system_wide_role(ENTERPRISE_ADMIN_ROLE)


def learner_role():
    """ Returns the enterprise learner role. """
    return get_or_create_system_wide_role(ENTERPRISE_LEARNER_ROLE)


def openedx_operator_role():
    """ Returns the enterprise openedx operator role. """
    return get_or_create_system_wide_role(ENTERPRISE_OPERATOR_ROLE)


def assign_learner_role(user, enterprise_customer=None, applies_to_all_contexts=False):
    """
    Assigns the given user the `enterprise_learner` role in the given customer.
    """
    return SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
        user=user,
        role=learner_role(),
        enterprise_customer=enterprise_customer,
        applies_to_all_contexts=applies_to_all_contexts,
    )


def assign_admin_role(user, enterprise_customer=None, applies_to_all_contexts=False):
    """
    Assigns the given user the `enterprise_admin` role in the given customer.
    """
    return SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
        user=user,
        role=admin_role(),
        enterprise_customer=enterprise_customer,
        applies_to_all_contexts=applies_to_all_contexts,
    )


def delete_role_assignment(user, role, enterprise_customer=None):
    """
    Deletes the given role assignment for the given user in the given enterprise customer.
    If `enterprise_customer` is null, will delete *every* role assignment for this user.
    """
    kwargs = {
        'user': user,
        'role': role,
    }
    if enterprise_customer:
        kwargs['enterprise_customer'] = enterprise_customer

    try:
        SystemWideEnterpriseUserRoleAssignment.objects.filter(**kwargs).delete()
    except SystemWideEnterpriseUserRoleAssignment.DoesNotExist:
        pass


def delete_learner_role_assignment(user, enterprise_customer=None):
    """
    Deletes the learner role assignment for the given user in the given enterprise customer.
    If `enterprise_customer` is null, will delete *every* learner role assignment for this user.
    """
    delete_role_assignment(user, learner_role(), enterprise_customer)


def delete_admin_role_assignment(user, enterprise_customer=None):
    """
    Deletes the admin role assignment for the given user in the given enterprise customer.
    If `enterprise_customer` is null, will delete *every* admin role assignment for this user.
    """
    delete_role_assignment(user, admin_role(), enterprise_customer)
