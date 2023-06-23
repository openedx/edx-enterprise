"""
Views for the ``enterprise-customer`` API endpoint.
"""

from urllib.parse import quote_plus, unquote

from edx_rbac.decorators import permission_required
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_409_CONFLICT,
)

from django.contrib import auth
from django.core import exceptions
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator

from enterprise import models
from enterprise.api.filters import EnterpriseLinkedUserFilterBackend
from enterprise.api.throttles import HighServiceUserThrottle
from enterprise.api.v1 import serializers
from enterprise.api.v1.decorators import require_at_least_one_query_parameter
from enterprise.api.v1.permissions import IsInEnterpriseGroup
from enterprise.api.v1.views.base_views import EnterpriseReadWriteModelViewSet
from enterprise.constants import PATHWAY_CUSTOMER_ADMIN_ENROLLMENT
from enterprise.errors import LinkUserToEnterpriseError, UnlinkUserFromEnterpriseError
from enterprise.logging import getEnterpriseLogger
from enterprise.utils import (
    enroll_subsidy_users_in_courses,
    get_best_mode_from_course_key,
    track_enrollment,
    validate_email_to_link,
)

User = auth.get_user_model()

LOGGER = getEnterpriseLogger(__name__)


class EnterpriseCustomerViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-customer`` API endpoint.
    """
    throttle_classes = (HighServiceUserThrottle, )
    queryset = models.EnterpriseCustomer.active_customers.all()
    serializer_class = serializers.EnterpriseCustomerSerializer
    filter_backends = EnterpriseReadWriteModelViewSet.filter_backends + (EnterpriseLinkedUserFilterBackend,)

    USER_ID_FILTER = 'enterprise_customer_users__user_id'
    FIELDS = (
        'uuid', 'slug', 'name', 'active', 'site', 'enable_data_sharing_consent',
        'enforce_data_sharing_consent',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        elif self.action == 'partial_update':
            return [permissions.IsAuthenticated()]
        else:
            return [permission() for permission in self.permission_classes]

    def get_serializer_class(self):
        if self.action == 'basic_list':
            return serializers.EnterpriseCustomerBasicSerializer
        return self.serializer_class

    @action(detail=False)
    # pylint: disable=unused-argument
    def basic_list(self, request, *arg, **kwargs):
        """
        Enterprise Customer's Basic data list without pagination

        Two query parameters are supported:
        - name_or_uuid: filter by name or uuid substring search in a single query parameter.
        Primarily used for frontend debounced input search.
        - startswith: filter by name starting with the given string
        """
        startswith = request.GET.get('startswith')
        name_or_uuid = request.GET.get('name_or_uuid')
        queryset = self.get_queryset().order_by('name')
        if startswith:
            queryset = queryset.filter(name__istartswith=startswith)
        if name_or_uuid:
            queryset = queryset.filter(Q(name__icontains=name_or_uuid) | Q(uuid__icontains=name_or_uuid))
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @permission_required('enterprise.can_access_admin_dashboard')
    def create(self, request, *args, **kwargs):
        """
        POST /enterprise/api/v1/enterprise-customer/
        """
        return super().create(request, *args, **kwargs)

    @permission_required('enterprise.can_access_admin_dashboard', fn=lambda request, pk: pk)
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @method_decorator(require_at_least_one_query_parameter('course_run_ids', 'program_uuids'))
    @action(detail=True)
    @permission_required('enterprise.can_view_catalog', fn=lambda request, pk, course_run_ids, program_uuids: pk)
    # pylint: disable=unused-argument
    def contains_content_items(self, request, pk, course_run_ids, program_uuids):
        """
        Return whether or not the specified content is available to the EnterpriseCustomer.

        Multiple course_run_ids and/or program_uuids query parameters can be sent to this view to check
        for their existence in the EnterpriseCustomerCatalogs associated with this EnterpriseCustomer.
        At least one course run key or program UUID value must be included in the request.
        """
        enterprise_customer = self.get_object()

        # Maintain plus characters in course key.
        course_run_ids = [unquote(quote_plus(course_run_id)) for course_run_id in course_run_ids]

        contains_content_items = False
        for catalog in enterprise_customer.enterprise_customer_catalogs.all():
            contains_course_runs = not course_run_ids or catalog.contains_courses(course_run_ids)
            contains_program_uuids = not program_uuids or catalog.contains_programs(program_uuids)
            if contains_course_runs and contains_program_uuids:
                contains_content_items = True
                break

        return Response({'contains_content_items': contains_content_items})

    @action(methods=['post'], permission_classes=[permissions.IsAuthenticated], detail=True)
    @permission_required('enterprise.can_enroll_learners', fn=lambda request, pk: pk)
    # pylint: disable=unused-argument
    def course_enrollments(self, request, pk):
        """
        Creates a course enrollment for an EnterpriseCustomerUser.
        """
        enterprise_customer = self.get_object()
        serializer = serializers.EnterpriseCustomerCourseEnrollmentsSerializer(
            data=request.data,
            many=True,
            context={
                'enterprise_customer': enterprise_customer,
                'request_user': request.user,
            }
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=HTTP_200_OK)

        return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    @permission_required('enterprise.can_enroll_learners', fn=lambda request, pk: pk)
    # pylint: disable=unused-argument, too-many-statements
    def enroll_learners_in_courses(self, request, pk):
        """
        Creates a set of enterprise enrollments for specified learners by bulk enrolling them in provided courses.
        This endpoint is not transactional, in that any one or more failures will not affect other successful
        enrollments made within the same request.

        Parameters:
            enrollments_info (list of dicts): an array of dictionaries, each containing the necessary information to
                create an enrollment based on a subsidy for a user in a specified course. Each dictionary must contain
                a user email (or user_id), a course run key, and either a UUID of the license that the learner is using
                to enroll with or a transaction ID related to Executive Education the enrollment. `licenses_info` is
                also accepted as a body param name.

                Example::

                    enrollments_info: [
                        {
                            'email': 'newuser@test.com',
                            'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                            'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae',
                        },
                        {
                            'email': 'newuser2@test.com',
                            'course_run_key': 'course-v2:edX+FunX+Fun_Course',
                            'transaction_id': '84kdbdbade7b4fcb838f8asjke8e18ae',
                        },
                        {
                            'user_id': 1234,
                            'course_run_key': 'course-v2:edX+SadX+Sad_Course',
                            'transaction_id': 'ba1f7b61951987dc2e1743fa4886b62d',
                        },
                        ...
                    ]

            discount (int): the percent discount to be applied to all enrollments. Defaults to 100.

        Returns:
            Success cases:
                - All users exist and are enrolled -
                    {'successes': [], 'pending': [], 'failures': []}, 201
                - Some or none of the users exist but are enrolled -
                    {'successes': [], 'pending': [], 'failures': []}, 202

            Failure cases:
                - Some or all of the users can't be enrolled, no users were enrolled -
                    {'successes': [], 'pending': [], 'failures': []}, 409

                - Some or all of the provided emails are invalid
                    {'successes': [], 'pending': [], 'failures': [] 'invalid_email_addresses': []}, 409
        """
        enterprise_customer = self.get_object()
        serializer = serializers.EnterpriseCustomerBulkSubscriptionEnrollmentsSerializer(
            data=request.data,
            context={
                'enterprise_customer': enterprise_customer,
                'request_user': request.user,
            }
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            error_message = "Something went wrong while validating bulk enrollment requests." \
                            "Received exception: {}".format(serializer.errors)
            LOGGER.warning(error_message)
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        user_id_errors = []
        email_errors = []
        serialized_data = serializer.validated_data
        enrollments_info = serialized_data.get('licenses_info', serialized_data.get('enrollments_info'))

        # Default subscription discount is 100%
        discount = serialized_data.get('discount', 100.00)

        # Retrieve and store course modes for each unique course provided
        course_runs_modes = {enrollment_info['course_run_key']: None for enrollment_info in enrollments_info}
        for course_run in course_runs_modes:
            course_runs_modes[course_run] = get_best_mode_from_course_key(course_run)

        emails = set()

        for info in enrollments_info:
            if 'user_id' in info:
                user = User.objects.filter(id=info['user_id']).first()
                if user:
                    info['email'] = user.email
                    emails.add(user.email)
                else:
                    user_id_errors.append(info['user_id'])
            else:
                emails.add(info['email'])
            info['course_mode'] = course_runs_modes[info['course_run_key']]

        for email in emails:
            try:
                validate_email_to_link(email, enterprise_customer, raise_exception=False)
            except exceptions.ValidationError:
                email_errors.append(email)

        for email in emails:
            try:
                models.EnterpriseCustomerUser.all_objects.link_user(enterprise_customer, email)
            except LinkUserToEnterpriseError:
                email_errors.append(email)

        # Remove the bad emails and bad user_ids from enrollments_info; don't attempt to enroll or link them.
        enrollments_info = [
            info for info in enrollments_info
            if info.get('email') not in email_errors and info.get('user_id') not in user_id_errors
        ]

        results = enroll_subsidy_users_in_courses(enterprise_customer, enrollments_info, discount)

        # collect the returned activation links for licenses which need activation
        activation_links = {}
        for result_kind in ['successes', 'pending']:
            for result in results[result_kind]:
                if result.get('activation_link') is not None:
                    activation_links[result['email']] = result.get('activation_link')

        for course_run in course_runs_modes:
            pending_users = {
                result.pop('user') for result in results['pending']
                if result['course_run_key'] == course_run and result.get('created')
            }
            existing_users = {
                result.pop('user') for result in results['successes']
                if result['course_run_key'] == course_run and result.get('created')
            }
            if len(pending_users | existing_users) > 0:
                LOGGER.info("Successfully bulk enrolled learners: {} into course {}".format(
                    pending_users | existing_users,
                    course_run,
                ))
                track_enrollment(PATHWAY_CUSTOMER_ADMIN_ENROLLMENT, request.user.id, course_run)
                if serializer.validated_data.get('notify'):
                    enterprise_customer.notify_enrolled_learners(
                        catalog_api_user=request.user,
                        course_id=course_run,
                        users=pending_users | existing_users,
                        admin_enrollment=True,
                        activation_links=activation_links,
                    )

        # Remove the user object from the results for any already existing enrollment cases (ie created = False) as
        # these are not JSON serializable
        existing_enrollments = []
        for result in results['pending']:
            already_enrolled_pending_user = result.pop('user', None)
            existing_enrollments.append(already_enrolled_pending_user)

        for result in results['successes']:
            already_enrolled_user = result.pop('user', None)
            existing_enrollments.append(already_enrolled_user)

        if existing_enrollments:
            LOGGER.info(
                f'Bulk enrollment request submitted for users: {existing_enrollments} who already have enrollments'
            )

        if user_id_errors:
            results['invalid_user_ids'] = user_id_errors
        if email_errors:
            results['invalid_email_addresses'] = email_errors

        if results['failures'] or email_errors or user_id_errors:
            return Response(results, status=HTTP_409_CONFLICT)
        if results['pending']:
            return Response(results, status=HTTP_202_ACCEPTED)
        return Response(results, status=HTTP_201_CREATED)

    @method_decorator(require_at_least_one_query_parameter('permissions'))
    @action(permission_classes=[permissions.IsAuthenticated, IsInEnterpriseGroup], detail=False)
    def with_access_to(self, request, *args, **kwargs):
        """
        Returns the list of enterprise customers the user has a specified group permission access to.
        """
        self.queryset = self.queryset.order_by('name')
        enterprise_id = self.request.query_params.get('enterprise_id', None)
        enterprise_slug = self.request.query_params.get('enterprise_slug', None)
        enterprise_name = self.request.query_params.get('search', None)

        if enterprise_id is not None:
            self.queryset = self.queryset.filter(uuid=enterprise_id)
        elif enterprise_slug is not None:
            self.queryset = self.queryset.filter(slug=enterprise_slug)
        elif enterprise_name is not None:
            self.queryset = self.queryset.filter(name__icontains=enterprise_name)
        return self.list(request, *args, **kwargs)

    @action(detail=False)
    @permission_required('enterprise.can_access_admin_dashboard')
    def dashboard_list(self, request, *args, **kwargs):
        """
        Supports listing dashboard enterprises for frontend-app-admin-portal.
        """
        self.queryset = self.queryset.order_by('name')
        enterprise_id = self.request.query_params.get('enterprise_id', None)
        enterprise_slug = self.request.query_params.get('enterprise_slug', None)
        enterprise_name = self.request.query_params.get('search', None)

        if enterprise_id is not None:
            self.queryset = self.queryset.filter(uuid=enterprise_id)
        elif enterprise_slug is not None:
            self.queryset = self.queryset.filter(slug=enterprise_slug)
        elif enterprise_name is not None:
            self.queryset = self.queryset.filter(name__icontains=enterprise_name)
        return self.list(request, *args, **kwargs)

    @action(methods=['patch'], detail=True, permission_classes=[permissions.IsAuthenticated])
    @permission_required('enterprise.can_access_admin_dashboard')
    def toggle_universal_link(self, request, pk=None):
        """
        Enables/Disables universal link config.
        """

        enterprise_customer = get_object_or_404(models.EnterpriseCustomer, uuid=pk)
        serializer = serializers.EnterpriseCustomerToggleUniversalLinkSerializer(
            data=request.data,
            context={
                'enterprise_customer': enterprise_customer,
                'request_user': request.user,
            }
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=HTTP_400_BAD_REQUEST)

        enable_universal_link = serializer.validated_data.get('enable_universal_link')

        if enterprise_customer.enable_universal_link == enable_universal_link:
            return Response({"detail": "No changes"}, status=HTTP_200_OK)

        enterprise_customer.toggle_universal_link(
            enable_universal_link,
        )

        response_body = {"enable_universal_link": enable_universal_link}
        headers = self.get_success_headers(response_body)
        return Response(response_body, status=HTTP_200_OK, headers=headers)

    @action(methods=['post'], detail=True, permission_classes=[permissions.IsAuthenticated])
    @permission_required('enterprise.can_access_admin_dashboard', fn=lambda request, pk: pk)
    def unlink_users(self, request, pk=None):  # pylint: disable=unused-argument
        """
        Unlinks users with the given emails from the enterprise.
        """

        serializer = serializers.EnterpriseCustomerUnlinkUsersSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        enterprise_customer = self.get_object()
        emails_to_unlink = serializer.data.get('user_emails', [])
        is_relinkable = serializer.data.get('is_relinkable', True)

        with transaction.atomic():
            for email in emails_to_unlink:
                try:
                    models.EnterpriseCustomerUser.objects.unlink_user(
                        enterprise_customer=enterprise_customer,
                        user_email=email,
                        is_relinkable=is_relinkable
                    )
                except (models.EnterpriseCustomerUser.DoesNotExist, models.PendingEnterpriseCustomerUser.DoesNotExist):
                    msg = "User with email {} does not exist in enterprise {}.".format(email, enterprise_customer)
                    LOGGER.warning(msg)
                except Exception as exc:
                    msg = "Could not unlink {} from {}".format(email, enterprise_customer)
                    raise UnlinkUserFromEnterpriseError(msg) from exc

        return Response(status=HTTP_200_OK)
