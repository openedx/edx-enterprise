"""
Mixins for Integrated Channel API Viewsets
"""
from uuid import UUID

from edx_rbac.mixins import PermissionRequiredForListingMixin
from rest_framework.exceptions import ParseError

from enterprise.constants import ENTERPRISE_ADMIN_ROLE
from enterprise.models import SystemWideEnterpriseUserRoleAssignment


class PermissionRequiredForIntegratedChannelMixin(PermissionRequiredForListingMixin):
    """
    `configuration_model` (class) - The RoleAssignmentClass against which DB-defined access is checked.
    """
    # fields that control permissions for 'list' actions
    list_lookup_field = 'enterprise_customer'
    allowed_roles = [ENTERPRISE_ADMIN_ROLE, ]
    role_assignment_class = SystemWideEnterpriseUserRoleAssignment

    @property
    def requested_enterprise_uuid(self):
        enterprise_customer_uuid = self.request.query_params.get('enterprise_customer')
        if not enterprise_customer_uuid:
            return None
        try:
            return UUID(enterprise_customer_uuid)
        except ValueError:
            raise ParseError('{} is not a valid uuid.'.format(enterprise_customer_uuid))

    def get_permission_object(self):
        """
        Used for "retrieve" actions. Determines the context (enterprise UUID) to check
        against for role-based permissions.
        """
        enterprise_customer_uuid = self.request.data.get('enterprise_customer_uuid')
        if enterprise_customer_uuid:
            return UUID(enterprise_customer_uuid)
        elif self.requested_enterprise_uuid:
            return self.requested_enterprise_uuid
        return None

    @property
    def base_queryset(self):
        """
        Required by the `PermissionRequiredForListingMixin`.
        For non-list actions, this is what's returned by `get_queryset()`.
        For list actions, some non-strict subset of this is what's returned by `get_queryset()`.
        """
        if not self.configuration_model:
            raise NotImplementedError
        kwargs = {}
        if self.requested_enterprise_uuid:
            kwargs.update({'enterprise_customer_id': self.requested_enterprise_uuid})
        return self.configuration_model.objects.filter(**kwargs)
