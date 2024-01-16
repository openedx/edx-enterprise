"""
Filters for enterprise API.
"""

from rest_framework import filters
from rest_framework.exceptions import ValidationError

from django.contrib import auth

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser, SystemWideEnterpriseUserRoleAssignment

User = auth.get_user_model()


class UserFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend for any view that needs to filter against the requesting user's ID.

    * Staff users will bypass this filter.
    * Non-staff users will receive only those objects that match their own user ID.

    This requires that `USER_ID_FILTER` be set in the view as a class variable, to identify
    the object's relationship to a user ID.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter only for the user's ID if non-staff.
        """
        if not request.user.is_staff:
            filter_kwargs = {view.USER_ID_FILTER: request.user.id}
            queryset = queryset.filter(**filter_kwargs)
        return queryset


class EnterpriseCourseEnrollmentFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend to return enrollments under the user's enterprise(s) only.

    * Staff users will bypass this filter.
    * Non-staff users will receive enrollments under their linked enterprises,
      only if they have the `enterprise.can_enroll_learners` permission.
    * Non-staff users without the `enterprise.can_enroll_learners` permission
      will receive only their own enrollments.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter out enrollments if learner is not linked
        """

        if request.user.is_staff:
            return queryset

        if request.user.has_perm('enterprise.can_enroll_learners'):
            enterprise_customers = EnterpriseCustomer.objects.filter(enterprise_customer_users__user_id=request.user.id)
            return queryset.filter(enterprise_customer_user__enterprise_customer__in=enterprise_customers)

        filter_kwargs = {
            view.USER_ID_FILTER: request.user.id,
        }

        return queryset.filter(**filter_kwargs)


class EnterpriseCustomerUserFilterBackend(filters.BaseFilterBackend):
    """
    Allow filtering on the enterprise customer user api endpoint.
    """

    def _filter_by_user_ids(self, request, queryset):
        """
        Filter queryset by a comma-delimited list of user ids.
        """

        user_ids = request.query_params.get('user_ids', None)
        if user_ids:
            user_ids = user_ids.strip(',').split(',')
            return queryset.filter(user_id__in=user_ids)

        return queryset

    def _filter_by_user_attributes(self, request, queryset):
        """
        Filter queryset by email or username.
        """
        email = request.query_params.get('email', None)
        username = request.query_params.get('username', None)

        query_params = {}

        if email:
            query_params.update(email=email)
        if username:
            query_params.update(username=username)

        if query_params:
            users = User.objects.filter(**query_params).values_list('id', flat=True)
            return queryset.filter(user_id__in=users)

        return queryset

    def _filter_by_enterprise_attributes(self, request, queryset):
        """
        Filter queryset by enterprise_customer_uuid or enterprise role.
        """
        enterprise_customer_uuid = request.query_params.get('enterprise_customer_uuid', None)
        role = request.query_params.get('role', None)

        query_params = {}

        if enterprise_customer_uuid:
            query_params.update(enterprise_customer_id=enterprise_customer_uuid)

        if role:
            role_assignment_filters = {'role__name': role}

            if not enterprise_customer_uuid:
                raise ValidationError('Cannot filter by role without providing enterprise_customer_uuid.')

            role_assignment_filters.update(enterprise_customer_id=enterprise_customer_uuid)

            users_with_role = SystemWideEnterpriseUserRoleAssignment.objects.filter(
                **role_assignment_filters
            ).values_list('user_id', flat=True)

            query_params.update(user_id__in=users_with_role)

        if query_params:
            return queryset.filter(**query_params)

        return queryset

    def filter_queryset(self, request, queryset, view):
        """
        Apply incoming filters only if user is staff. If not, only filter by user's ID.
        """
        if request.user.is_staff:
            queryset = self._filter_by_user_attributes(request, queryset)
            queryset = self._filter_by_enterprise_attributes(request, queryset)
            queryset = self._filter_by_user_ids(request, queryset)
        else:
            queryset = queryset.filter(user_id=request.user.id)

        return queryset


class EnterpriseLinkedUserFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend to return user's linked enterprises only

    * Staff users will bypass this filter.
    * Non-staff users will receive only their linked enterprises.
    """

    def filter_queryset(self, request, queryset, view):
        """
        Filter out enterprise customer if learner is not linked
        """
        if not request.user.is_staff:
            filter_kwargs = {
                view.USER_ID_FILTER: request.user.id,
                'enterprise_customer_users__linked': 1
            }
            queryset = queryset.filter(**filter_kwargs)

        return queryset


class EnterpriseCustomerInviteKeyFilterBackend(filters.BaseFilterBackend):
    """
    Filter backend to return invite keys under the user's enterprise(s) only.
    Supports filtering by enterprise_customer_uuid.

    * Staff users will bypass this filter.
    """

    def filter_queryset(self, request, queryset, view):
        query_params = {}

        if not request.user.is_staff:
            user_enterprise_customer_uuids = [
                ec.enterprise_customer_id for ec in EnterpriseCustomerUser.objects.filter(user_id=request.user.id)
            ]
            query_params.update(enterprise_customer_id__in=user_enterprise_customer_uuids)

        enterprise_customer_uuid = request.query_params.get('enterprise_customer_uuid', None)
        if enterprise_customer_uuid:
            query_params.update(enterprise_customer_id=enterprise_customer_uuid)

        return queryset.filter(**query_params)
