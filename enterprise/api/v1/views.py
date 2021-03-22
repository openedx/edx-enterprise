# -*- coding: utf-8 -*-
"""
Views for enterprise api version 1 endpoint.
"""

from logging import getLogger
from smtplib import SMTPException

import requests
from django_filters.rest_framework import DjangoFilterBackend
from edx_rbac.decorators import permission_required
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from rest_framework.views import APIView
from rest_framework_xml.renderers import XMLRenderer
from six.moves.urllib.parse import quote_plus, unquote  # pylint: disable=import-error,ungrouped-imports

from django.apps import apps
from django.conf import settings
from django.core import exceptions, mail
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from enterprise import models
from enterprise.api.filters import (
    EnterpriseCustomerUserFilterBackend,
    EnterpriseLinkedUserFilterBackend,
    UserFilterBackend,
)
from enterprise.api.throttles import ServiceUserThrottle
from enterprise.api.utils import (
    create_message_body,
    get_ent_cust_from_report_config_uuid,
    get_enterprise_customer_from_catalog_id,
    get_enterprise_customer_from_user_id,
)
from enterprise.api.v1 import serializers
from enterprise.api.v1.decorators import require_at_least_one_query_parameter
from enterprise.api.v1.permissions import IsInEnterpriseGroup
from enterprise.api_client.ecommerce import EcommerceApiClient
from enterprise.api_client.lms import EnrollmentApiClient
from enterprise.constants import COURSE_KEY_URL_PATTERN
from enterprise.errors import CodesAPIRequestError
from enterprise.utils import (
    NotConnectedToOpenEdX,
    enroll_licensed_users_in_courses,
    get_best_mode_from_course_key,
    get_ecommerce_worker_user,
    get_request_value,
    validate_email_to_link,
)
from enterprise_learner_portal.utils import CourseRunProgressStatuses, get_course_run_status

try:
    from common.djangoapps.course_modes.models import CourseMode
    from lms.djangoapps.certificates.api import get_certificate_for_user
    from openedx.core.djangoapps.content.course_overviews.api import get_course_overviews
except ImportError:
    get_course_overviews = None
    get_certificate_for_user = None
    CourseMode = None


LOGGER = getLogger(__name__)


class EnterpriseViewSet:
    """
    Base class for all Enterprise view sets.
    """

    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    def ensure_data_exists(self, request, data, error_message=None):
        """
        Ensure that the wrapped API client's response brings us valid data. If not, raise an error and log it.
        """
        if not data:
            error_message = (
                error_message or "Unable to fetch API response from endpoint '{}'.".format(request.get_full_path())
            )
            LOGGER.error(error_message)
            raise NotFound(error_message)


class EnterpriseWrapperApiViewSet(EnterpriseViewSet, viewsets.ViewSet):
    """
    Base class for attribute and method definitions common to all view sets which wrap external APIs.
    """


class EnterpriseModelViewSet(EnterpriseViewSet):
    """
    Base class for attribute and method definitions common to all view sets.
    """

    filter_backends = (filters.OrderingFilter, DjangoFilterBackend, UserFilterBackend,)
    permission_classes = (permissions.IsAuthenticated, permissions.DjangoModelPermissions,)
    USER_ID_FILTER = 'id'


class EnterpriseReadOnlyModelViewSet(EnterpriseModelViewSet, viewsets.ReadOnlyModelViewSet):
    """
    Base class for all read only Enterprise model view sets.
    """


class EnterpriseReadWriteModelViewSet(EnterpriseModelViewSet, viewsets.ModelViewSet):
    """
    Base class for all read/write Enterprise model view sets.
    """

    permission_classes = (permissions.IsAuthenticated, permissions.DjangoModelPermissions,)


class EnterpriseCustomerViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-customer`` API endpoint.
    """

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

    def get_serializer_class(self):
        if self.action == 'basic_list':
            return serializers.EnterpriseCustomerBasicSerializer
        return self.serializer_class

    @action(detail=False)
    # pylint: disable=invalid-name,unused-argument
    def basic_list(self, request, *arg, **kwargs):
        """
            Enterprise Customer's Basic data list without pagination
        """
        startswith = request.GET.get('startswith')
        queryset = self.get_queryset().order_by('name')
        if startswith:
            queryset = queryset.filter(name__istartswith=startswith)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @method_decorator(require_at_least_one_query_parameter('course_run_ids', 'program_uuids'))
    @action(detail=True)
    @permission_required('enterprise.can_view_catalog', fn=lambda request, pk, course_run_ids, program_uuids: pk)
    # pylint: disable=invalid-name,unused-argument
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
    # pylint: disable=invalid-name,unused-argument
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
    # pylint: disable=invalid-name,unused-argument
    def enroll_learners_in_courses(self, request, pk):
        """
        Creates a set of licensed enterprise_learners by bulk enrolling them in all specified courses. This endpoint is
        not transactional, in that any one or more failures will not affect other successful enrollments made within
        the same request.

        Expected params:
            - licenses_info (list of dicts): an array of dictionaries, each containing the necessary information to
            create a licenced enrollment for a user in a specified course. Each dictionary must contain a user email, a
            course run key, and a UUID of the license that the learner is using to enroll with.
            Example:
                licenses_info: [
                    {
                        'email': 'newuser@test.com',
                        'course_run_key': 'course-v1:edX+DemoX+Demo_Course',
                        'license_uuid': '5b77bdbade7b4fcb838f8111b68e18ae'
                    },
                    ...
                ]

        Optional params:
            - discount (int): the percent discount to be applied to all enrollments. Defaults to 100.

        Expected Return Values:
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

        email_errors = []
        licenses_info = serializer.validated_data.get('licenses_info')

        # Default subscription discount is 100%
        discount = serializer.validated_data.get('discount', 100.00)

        emails = set()

        # Retrieve and store course modes for each unique course provided
        course_runs_modes = {license_info['course_run_key']: None for license_info in licenses_info}
        for course_run in course_runs_modes:
            course_runs_modes[course_run] = get_best_mode_from_course_key(course_run)

        for index, info in enumerate(licenses_info):
            emails.add(info['email'])
            licenses_info[index]['course_mode'] = course_runs_modes[info['course_run_key']]

        for email in emails:
            try:
                validate_email_to_link(email, enterprise_customer, raise_exception=False)
            except exceptions.ValidationError:
                email_errors.append(email)

        # Remove the bad emails from licenses_info and emails, don't attempt to enroll or link bad emails.
        for errored_user in email_errors:
            licenses_info[:] = [info for info in licenses_info if info['email'] != errored_user]
            emails.remove(errored_user)

        for email in emails:
            models.EnterpriseCustomerUser.objects.link_user(enterprise_customer, email)

        results = enroll_licensed_users_in_courses(enterprise_customer, licenses_info, discount)

        for course_run in course_runs_modes:
            pending_users = {
                result.pop('user') for result in results['pending'] if result['course_run_key'] == course_run
            }
            existing_users = {
                result.pop('user') for result in results['successes'] if result['course_run_key'] == course_run
            }
            LOGGER.info("Successfully bulk enrolled learners: {}".format(pending_users | existing_users))
            if serializer.validated_data.get('notify'):
                enterprise_customer.notify_enrolled_learners(
                    catalog_api_user=request.user,
                    course_id=course_run,
                    users=pending_users | existing_users,
                )

            self._create_ecom_orders_for_enrollments(
                course_run,
                course_runs_modes[course_run],
                discount,
                serializer.validated_data.get('salesforce_id'),
                existing_users,
            )
        if email_errors:
            results['invalid_email_addresses'] = email_errors

        if results['failures'] or email_errors:
            return Response(results, status=HTTP_409_CONFLICT)
        if results['pending']:
            return Response(results, status=HTTP_202_ACCEPTED)
        return Response(results, status=HTTP_201_CREATED)

    def _create_ecom_orders_for_enrollments(self,
                                            course_run_key,
                                            mode,
                                            discount,
                                            salesforce_id,
                                            succeeded_enrollments):
        """
        Create ecommerce enrollment order for provided enrollments
        """
        paid_modes = ['verified', 'professional']
        enterprise_customer = self.get_object()
        if mode in paid_modes:
            enrollments = [{
                "lms_user_id": success.id,
                "email": success.email,
                "username": success.username,
                "course_run_key": course_run_key,
                "discount_percentage": float(discount),
                "enterprise_customer_name": enterprise_customer.name,
                "enterprise_customer_uuid": str(enterprise_customer.uuid),
                "mode": mode,
                "sales_force_id": salesforce_id,
            } for success in succeeded_enrollments]
            EcommerceApiClient(get_ecommerce_worker_user()).create_manual_enrollment_orders(enrollments)

    @method_decorator(require_at_least_one_query_parameter('permissions'))
    @action(permission_classes=[permissions.IsAuthenticated, IsInEnterpriseGroup], detail=False)
    def with_access_to(self, request, *args, **kwargs):  # pylint: disable=invalid-name,unused-argument
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
    def dashboard_list(self, request, *args, **kwargs):  # pylint: disable=invalid-name,unused-argument
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


class EnterpriseCourseEnrollmentViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-course-enrollment`` API endpoint.
    """

    queryset = models.EnterpriseCourseEnrollment.objects.all()

    USER_ID_FILTER = 'enterprise_customer_user__user_id'
    FIELDS = (
        'enterprise_customer_user', 'course_id'
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    def get_serializer_class(self):
        """
        Use a special serializer for any requests that aren't read-only.
        """
        if self.request.method in ('GET',):
            return serializers.EnterpriseCourseEnrollmentReadOnlySerializer
        return serializers.EnterpriseCourseEnrollmentWriteSerializer


class EnrollmentModificationException(Exception):
    """
    An exception that represents an error when modifying the state
    of an enrollment via the EnrollmentApiClient.
    """


class LicensedEnterpriseCourseEnrollmentViewSet(EnterpriseWrapperApiViewSet):
    """
    API views for the ``licensed-enterprise-course-enrollment`` API endpoint.
    """

    queryset = models.LicensedEnterpriseCourseEnrollment.objects.all()
    serializer_class = serializers.LicensedEnterpriseCourseEnrollmentReadOnlySerializer
    REQ_EXP_LICENSE_UUIDS_PARAM = 'expired_license_uuids'

    class EnrollmentTerminationStatus:
        """
        Defines statuses related to enrollment states during the course unenrollment process.
        """
        COURSE_COMPLETED = 'course already completed'
        MOVED_TO_AUDIT = 'moved to audit'
        UNENROLLED = 'unenrolled'
        UNENROLL_FAILED = 'unenroll_user_from_course returned false.'

    @staticmethod
    def _validate_license_revoke_data(request_data):
        """
        Ensures the request data contains the necessary information.

        Arguments:
            request_data (dict): A dictionary of data passed to the request
        """
        user_id = request_data.get('user_id')
        enterprise_id = request_data.get('enterprise_id')

        if not user_id or not enterprise_id:
            msg = 'user_id and enterprise_id must be provided.'
            return Response(msg, status=status.HTTP_400_BAD_REQUEST)

        return None

    @staticmethod
    def _has_user_completed_course_run(enterprise_enrollment, course_overview):
        """
        Returns True if the user who is enrolled in the given course has already
        completed this course, false otherwise.  The course may be "completed"
        if the user earned a certificate, or if the course run has ended.

        Args:
            enterprise_enrollment (EnterpriseCourseEnrollment): The enrollment object for which we check
                if the associated user has completed the given course.
            course_overview (CourseOverview): The course overview of which we are checking completion.  We need this
                to check certificate status.  It's a model defined in edx-platform.
        """
        certificate_info = get_certificate_for_user(
            enterprise_enrollment.enterprise_customer_user.username,
            course_overview.get('id'),
        ) or {}
        course_run_status = get_course_run_status(
            course_overview,
            certificate_info,
            enterprise_enrollment,
        )

        return course_run_status == CourseRunProgressStatuses.COMPLETED

    def _enrollments_by_course_for_licensed_user(self, enterprise_customer_user):
        """
        Helper method to return a dictionary mapping course ids to EnterpriseCourseEnrollments
        for each licensed enrollment associated with the given enterprise user.

        Args:
            enterprise_customer_user (EnterpriseCustomerUser): The user for which we are fetching enrollments.
        """
        licensed_enrollments = models.LicensedEnterpriseCourseEnrollment.enrollments_for_user(
            enterprise_customer_user
        )
        return {
            enrollment.enterprise_course_enrollment.course_id: enrollment.enterprise_course_enrollment
            for enrollment in licensed_enrollments
        }

    def _terminate_enrollment(self, enrollment_api_client, enterprise_enrollment, course_overview):
        """
        Helper method that switches the given enrollment to audit track, or, if
        no audit track exists for the given course, deletes the enrollment.
        Will do nothing if the user has already "completed" the course run.

        Args:
            enrollment_api_client (EnrollmentApiClient): The client with which we make requests to modify enrollments.
            enterprise_enrollment (EnterpriseCourseEnrollment): The enterprise enrollment which we attempt to revoke.
            course_overview (CourseOverview): The course overview object associated with the enrollment. Used
                to check for course completion.
        """
        course_run_id = course_overview.get('id')
        enterprise_customer_user = enterprise_enrollment.enterprise_customer_user
        audit_mode = CourseMode.AUDIT
        enterprise_id = enterprise_customer_user.enterprise_customer.uuid

        log_message_kwargs = {
            'user': enterprise_customer_user.username,
            'enterprise': enterprise_id,
            'course_id': course_run_id,
            'mode': audit_mode,
        }

        if self._has_user_completed_course_run(enterprise_enrollment, course_overview):
            LOGGER.info(
                'enrollment termination: not updating enrollment in {course_id} for User {user} '
                'in Enterprise {enterprise}, course is already complete.'.format(**log_message_kwargs)
            )
            return self.EnrollmentTerminationStatus.COURSE_COMPLETED

        if CourseMode.mode_for_course(course_run_id, audit_mode):
            try:
                enrollment_api_client.update_course_enrollment_mode_for_user(
                    username=enterprise_customer_user.username,
                    course_id=course_run_id,
                    mode=audit_mode,
                )
                LOGGER.info(
                    'Enrollment termination: updated LMS enrollment for User {user} and Enterprise {enterprise} '
                    'in Course {course_id} to Course Mode {mode}.'.format(**log_message_kwargs)
                )
                return self.EnrollmentTerminationStatus.MOVED_TO_AUDIT
            except Exception as exc:  # pylint: disable=broad-except
                msg = (
                    'Enrollment termination: unable to update LMS enrollment for User {user} and '
                    'Enterprise {enterprise} in Course {course_id} to Course Mode {mode} because: {reason}'.format(
                        reason=str(exc),
                        **log_message_kwargs
                    )
                )
                LOGGER.error('{msg}: {exc}'.format(msg=msg, exc=exc))
                raise EnrollmentModificationException(msg) from exc
        else:
            try:
                successfully_unenrolled = enrollment_api_client.unenroll_user_from_course(
                    username=enterprise_customer_user.username,
                    course_id=course_run_id,
                )
                if not successfully_unenrolled:
                    raise Exception(self.EnrollmentTerminationStatus.UNENROLL_FAILED)

                LOGGER.info(
                    'Enrollment termination: successfully unenrolled User {user}, in Enterprise {enterprise} '
                    'from Course {course_id} that contains no audit mode.'.format(**log_message_kwargs)
                )
                return self.EnrollmentTerminationStatus.UNENROLLED
            except Exception as exc:  # pylint: disable=broad-except
                msg = (
                    'Enrollment termination: unable to unenroll User {user} in Enterprise {enterprise} '
                    'from Course {course_id}  because: {reason}'.format(
                        reason=str(exc),
                        **log_message_kwargs
                    )
                )
                LOGGER.error('{msg}: {exc}'.format(msg=msg, exc=exc))
                raise EnrollmentModificationException(msg) from exc

    @action(methods=['post'], detail=False)
    @permission_required('enterprise.can_access_admin_dashboard', fn=lambda request: request.data.get('enterprise_id'))
    def license_revoke(self, request, *args, **kwargs):  # pylint: disable=W0613
        """
        Changes the mode for a user's licensed enterprise course enrollments to the "audit" course mode,
        or unenroll the user if no audit mode exists for a given course.

        Will return a response with status 200 if no errors were encountered while modifying the course enrollment,
        or a 422 if any errors were encountered.  The content of the response is of the form:

        {
            'course-v1:puppies': {'success': true, 'message': 'unenrolled'},
            'course-v1:birds': {'success': true, 'message': 'moved to audit'},
            'course-v1:kittens': {'success': true, 'message': 'course already completed'},
            'course-v1:snakes': {'success': false, 'message': 'unenroll_user_from_course returned false'},
            'course-v1:lizards': {'success': false, 'message': 'Some other exception'},
        }

        The first four messages are the values of constants that a client may expect to receive and parse accordingly.
        """
        if not all([get_course_overviews, get_certificate_for_user, CourseMode]):
            raise NotConnectedToOpenEdX(
                _('To use this endpoint, this package must be '
                  'installed in an Open edX environment.')
            )

        request_data = request.data.copy()
        invalid_response = self._validate_license_revoke_data(request_data)
        if invalid_response:
            return invalid_response

        user_id = request_data.get('user_id')
        enterprise_id = request_data.get('enterprise_id')

        enterprise_customer_user = get_object_or_404(
            models.EnterpriseCustomerUser,
            user_id=user_id,
            enterprise_customer=enterprise_id,
        )
        enrollments_by_course_id = self._enrollments_by_course_for_licensed_user(enterprise_customer_user)

        enrollment_api_client = EnrollmentApiClient()

        revocation_results = {}
        any_failures = False
        for course_overview in get_course_overviews(list(enrollments_by_course_id.keys())):
            course_id = str(course_overview.get('id'))
            enterprise_enrollment = enrollments_by_course_id.get(course_id)
            try:
                revocation_status = self._terminate_enrollment(
                    enrollment_api_client, enterprise_enrollment, course_overview
                )
                revocation_results[course_id] = {'success': True, 'message': revocation_status}
                if revocation_status != self.EnrollmentTerminationStatus.COURSE_COMPLETED:
                    enterprise_enrollment.license.revoke()
            except EnrollmentModificationException as exc:
                revocation_results[course_id] = {'success': False, 'message': str(exc)}
                any_failures = True
                enterprise_enrollment.license.revoke()

        status_code = status.HTTP_200_OK if not any_failures else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(revocation_results, status=status_code)

    @action(methods=['post'], detail=False)
    @permission_required('enterprise.can_enroll_learners')
    def bulk_licensed_enrollments_expiration(self, request):
        """
        Changes the mode for licensed enterprise course enrollments to the "audit" course mode,
        or unenroll the user if no audit mode exists for each expired license uuid
        """
        expired_license_uuids = get_request_value(request, self.REQ_EXP_LICENSE_UUIDS_PARAM, '')

        if not expired_license_uuids:
            return Response(
                'Parameter {} must be provided'.format(self.REQ_EXP_LICENSE_UUIDS_PARAM),
                status=status.HTTP_400_BAD_REQUEST
            )

        licensed_enrollments = models.LicensedEnterpriseCourseEnrollment.objects.filter(
            license_uuid__in=expired_license_uuids
        ).select_related('enterprise_course_enrollment')

        enrollment_api_client = EnrollmentApiClient()
        course_overviews = get_course_overviews(
            list(licensed_enrollments.values_list('enterprise_course_enrollment__course_id', flat=True))
        )
        indexed_overviews = {overview.get('id'): overview for overview in course_overviews}

        any_failures = False
        for licensed_enrollment in licensed_enrollments:
            enterprise_course_enrollment = licensed_enrollment.enterprise_course_enrollment
            course_id = enterprise_course_enrollment.course_id
            course_overview = indexed_overviews.get(course_id)
            try:
                termination_status = self._terminate_enrollment(
                    enrollment_api_client, enterprise_course_enrollment, course_overview
                )
                LOGGER.info((
                    "EnterpriseCourseEnrollment record with enterprise license %s "
                    "unenrolled to status %s."
                ), enterprise_course_enrollment.licensed_with.license_uuid, termination_status)
                if termination_status != self.EnrollmentTerminationStatus.COURSE_COMPLETED:
                    enterprise_course_enrollment.saved_for_later = True
                    enterprise_course_enrollment.save()
            except EnrollmentModificationException as exc:
                LOGGER.error((
                    "Failed to unenroll EnterpriseCourseEnrollment record for enterprise license %s. "
                    "error message %s."
                ), enterprise_course_enrollment.licensed_with.license_uuid, str(exc))
                any_failures = True

        status_code = status.HTTP_200_OK if not any_failures else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(status=status_code)


class EnterpriseCustomerUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-learner`` API endpoint.
    """

    queryset = models.EnterpriseCustomerUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend, EnterpriseCustomerUserFilterBackend)

    FIELDS = (
        'enterprise_customer', 'user_id', 'active',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    def get_serializer_class(self):
        """
        Use a flat serializer for any requests that aren't read-only.
        """
        if self.request.method in ('GET',):
            return serializers.EnterpriseCustomerUserReadOnlySerializer
        return serializers.EnterpriseCustomerUserWriteSerializer


class PendingEnterpriseCustomerUserViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``pending-enterprise-learner`` API endpoint.
    Requires staff permissions
    """
    queryset = models.PendingEnterpriseCustomerUser.objects.all()
    filter_backends = (filters.OrderingFilter, DjangoFilterBackend)
    serializer_class = serializers.PendingEnterpriseCustomerUserSerializer
    permission_classes = (permissions.IsAuthenticated, permissions.IsAdminUser)

    FIELDS = (
        'enterprise_customer', 'user_email',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    UNIQUE = 'unique'
    USER_EXISTS_ERROR = 'EnterpriseCustomerUser record already exists'

    def _get_return_status(self, serializer, many):
        """
        Run serializer validation and get return status
        """
        return_status = None
        serializer.is_valid(raise_exception=True)
        if not many:
            _, created = serializer.save()
            return_status = status.HTTP_201_CREATED if created else status.HTTP_204_NO_CONTENT
            return return_status

        data_list = serializer.save()
        for _, created in data_list:
            if created:
                return status.HTTP_201_CREATED
        return status.HTTP_204_NO_CONTENT

    def create(self, request, *args, **kwargs):
        """
        Creates a PendingEnterpriseCustomerUser if no EnterpriseCustomerUser for the given (customer, email)
        combination(s) exists.
        Can accept one user or a list of users.

        Returns 201 if any users were created, 204 if no users were created.
        """
        serializer = self.get_serializer(data=request.data, many=isinstance(request.data, list))
        return_status = self._get_return_status(serializer, many=isinstance(request.data, list))
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=return_status, headers=headers)


class PendingEnterpriseCustomerUserEnterpriseAdminViewSet(PendingEnterpriseCustomerUserViewSet):
    """
    Viewset for allowing enterpise admins to create linked learners
    Endpoint url: link_pending_enterprise_users/(?P<enterprise_uuid>[A-Za-z0-9-]+)/?$
    Admin must be an administrator for the enterprise in question
    """
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.LinkLearnersSerializer

    @action(methods=['post'], detail=False)
    @permission_required('enterprise.can_access_admin_dashboard', fn=lambda request, enterprise_uuid: enterprise_uuid)
    def link_learners(self, request, enterprise_uuid):
        """
        Creates a PendingEnterpriseCustomerUser if no EnterpriseCustomerUser for the given (customer, email)
        combination(s) exists.
        Can accept one user or a list of users.

        Returns 201 if any users were created, 204 if no users were created.
        """
        context = {'enterprise_customer__uuid': enterprise_uuid}
        serializer = self.get_serializer(
            data=request.data,
            many=isinstance(request.data, list),
            context=context,
        )
        return_status = self._get_return_status(serializer, many=isinstance(request.data, list))
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=return_status, headers=headers)


class EnterpriseCustomerBrandingConfigurationViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API views for the ``enterprise-customer-branding`` API endpoint.
    """

    queryset = models.EnterpriseCustomerBrandingConfiguration.objects.all()
    serializer_class = serializers.EnterpriseCustomerBrandingConfigurationSerializer

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'enterprise_customer__slug',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS
    lookup_field = 'enterprise_customer__slug'


class EnterpriseCustomerCatalogViewSet(EnterpriseReadOnlyModelViewSet):
    """
    API Views for performing search through course discovery at the ``enterprise_catalogs`` API endpoint.
    """
    queryset = models.EnterpriseCustomerCatalog.objects.all()

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'uuid', 'enterprise_customer',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS
    renderer_classes = (JSONRenderer, XMLRenderer,)

    @permission_required('enterprise.can_view_catalog', fn=lambda request, *args, **kwargs: None)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)  # pylint: disable=no-member

    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_catalog_id(kwargs['pk']))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_serializer_class(self):
        view_action = getattr(self, 'action', None)
        if view_action == 'retrieve':
            return serializers.EnterpriseCustomerCatalogDetailSerializer
        return serializers.EnterpriseCustomerCatalogSerializer

    @method_decorator(require_at_least_one_query_parameter('course_run_ids', 'program_uuids'))
    @action(detail=True)
    # pylint: disable=invalid-name,unused-argument
    def contains_content_items(self, request, pk, course_run_ids, program_uuids):
        """
        Return whether or not the EnterpriseCustomerCatalog contains the specified content.

        Multiple course_run_ids and/or program_uuids query parameters can be sent to this view to check
        for their existence in the EnterpriseCustomerCatalog. At least one course run key
        or program UUID value must be included in the request.
        """
        enterprise_customer_catalog = self.get_object()

        # Maintain plus characters in course key.
        course_run_ids = [unquote(quote_plus(course_run_id)) for course_run_id in course_run_ids]

        contains_content_items = True
        if course_run_ids:
            contains_content_items = enterprise_customer_catalog.contains_courses(course_run_ids)
        if program_uuids:
            contains_content_items = (
                contains_content_items and
                enterprise_customer_catalog.contains_programs(program_uuids)
            )

        return Response({'contains_content_items': contains_content_items})

    @action(detail=True, url_path='courses/{}'.format(COURSE_KEY_URL_PATTERN))
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, course_key: get_enterprise_customer_from_catalog_id(pk))
    def course_detail(self, request, pk, course_key):  # pylint: disable=invalid-name,unused-argument
        """
        Return the metadata for the specified course.

        The course needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        course = enterprise_customer_catalog.get_course(course_key)
        if not course:
            error_message = _(
                '[Enterprise API] CourseKey not found in the Catalog. Course: {course_key}, Catalog: {catalog_id}'
            ).format(
                course_key=course_key,
                catalog_id=enterprise_customer_catalog.uuid,
            )
            LOGGER.warning(error_message)
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.CourseDetailSerializer(course, context=context)
        return Response(serializer.data)

    @action(detail=True, url_path='course_runs/{}'.format(settings.COURSE_ID_PATTERN))
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, course_id: get_enterprise_customer_from_catalog_id(pk))
    def course_run_detail(self, request, pk, course_id):  # pylint: disable=invalid-name,unused-argument
        """
        Return the metadata for the specified course run.

        The course run needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        course_run = enterprise_customer_catalog.get_course_run(course_id)
        if not course_run:
            error_message = _(
                '[Enterprise API] CourseRun not found in the Catalog. CourseRun: {course_id}, Catalog: {catalog_id}'
            ).format(
                course_id=course_id,
                catalog_id=enterprise_customer_catalog.uuid,
            )
            LOGGER.warning(error_message)
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.CourseRunDetailSerializer(course_run, context=context)
        return Response(serializer.data)

    @action(detail=True, url_path='programs/(?P<program_uuid>[^/]+)')
    @permission_required(
        'enterprise.can_view_catalog',
        fn=lambda request, pk, program_uuid: get_enterprise_customer_from_catalog_id(pk))
    def program_detail(self, request, pk, program_uuid):  # pylint: disable=invalid-name,unused-argument
        """
        Return the metadata for the specified program.

        The program needs to be included in the specified EnterpriseCustomerCatalog
        in order for metadata to be returned from this endpoint.
        """
        enterprise_customer_catalog = self.get_object()
        program = enterprise_customer_catalog.get_program(program_uuid)
        if not program:
            error_message = _(
                '[Enterprise API] Program not found in the Catalog. Program: {program_uuid}, Catalog: {catalog_id}'
            ).format(
                program_uuid=program_uuid,
                catalog_id=enterprise_customer_catalog.uuid,
            )
            LOGGER.warning(error_message)
            raise Http404

        context = self.get_serializer_context()
        context['enterprise_customer_catalog'] = enterprise_customer_catalog
        serializer = serializers.ProgramDetailSerializer(program, context=context)
        return Response(serializer.data)


class EnterpriseCustomerReportingConfigurationViewSet(EnterpriseReadWriteModelViewSet):
    """
    API views for the ``enterprise-customer-reporting`` API endpoint.
    """

    queryset = models.EnterpriseCustomerReportingConfiguration.objects.all()
    serializer_class = serializers.EnterpriseCustomerReportingConfigurationSerializer
    lookup_field = 'uuid'
    permission_classes = [permissions.IsAuthenticated]

    USER_ID_FILTER = 'enterprise_customer__enterprise_customer_users__user_id'
    FIELDS = (
        'enterprise_customer',
    )
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_ent_cust_from_report_config_uuid(kwargs['uuid']))
    def retrieve(self, request, *args, **kwargs):
        # pylint: disable=no-member
        return super().retrieve(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_user_id(request.user.id))
    def list(self, request, *args, **kwargs):
        # pylint: disable=no-member
        return super().list(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_enterprise_customer_from_user_id(request.user.id))
    def create(self, request, *args, **kwargs):
        config_data = request.data.copy()
        config_data['enterprise_customer_id'] = get_enterprise_customer_from_user_id(request.user.id)
        serializer = self.get_serializer(data=config_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_ent_cust_from_report_config_uuid(kwargs['uuid']))
    def update(self, request, *args, **kwargs):
        # pylint: disable=no-member
        return super().update(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_ent_cust_from_report_config_uuid(kwargs['uuid']))
    def partial_update(self, request, *args, **kwargs):
        # pylint: disable=no-member
        return super().partial_update(request, *args, **kwargs)

    @permission_required(
        'enterprise.can_manage_reporting_config',
        fn=lambda request, *args, **kwargs: get_ent_cust_from_report_config_uuid(kwargs['uuid']))
    def destroy(self, request, *args, **kwargs):
        # pylint: disable=no-member
        return super().destroy(request, *args, **kwargs)


class CatalogQueryView(APIView):
    """
    View for enterprise catalog query.
    This will be called from django admin tool to populate `content_filter` field of `EnterpriseCustomerCatalog` model.
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    http_method_names = ['get']

    def get(self, request, catalog_query_id):
        """
        API endpoint for fetching an enterprise catalog query.
        """
        try:
            catalog_query = models.EnterpriseCatalogQuery.objects.get(pk=catalog_query_id)
        except models.EnterpriseCatalogQuery.DoesNotExist:
            return Response({"detail": "Could not find enterprise catalog query."}, status=HTTP_404_NOT_FOUND)
        return Response(catalog_query.content_filter, status=HTTP_200_OK)


class CouponCodesView(APIView):
    """
    API to request coupon codes.
    """
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (JwtAuthentication, SessionAuthentication,)
    throttle_classes = (ServiceUserThrottle,)

    REQUIRED_PARAM_EMAIL = 'email'
    REQUIRED_PARAM_ENTERPRISE_NAME = 'enterprise_name'
    OPTIONAL_PARAM_NUMBER_OF_CODES = 'number_of_codes'
    OPTIONAL_PARAM_NOTES = 'notes'

    MISSING_REQUIRED_PARAMS_MSG = "Some required parameter(s) missing: {}"

    def get_required_query_params(self, request):
        """
        Gets ``email``, ``enterprise_name``, ``number_of_codes``, and ``notes``,
        which are the relevant parameters for this API endpoint.

        :param request: The request to this endpoint.
        :return: The ``email``, ``enterprise_name``, ``number_of_codes`` and ``notes`` from the request.
        """
        email = get_request_value(request, self.REQUIRED_PARAM_EMAIL, '')
        enterprise_name = get_request_value(request, self.REQUIRED_PARAM_ENTERPRISE_NAME, '')
        number_of_codes = get_request_value(request, self.OPTIONAL_PARAM_NUMBER_OF_CODES, '')
        notes = get_request_value(request, self.OPTIONAL_PARAM_NOTES, '')
        if not (email and enterprise_name):
            raise CodesAPIRequestError(
                self.get_missing_params_message([
                    (self.REQUIRED_PARAM_EMAIL, bool(email)),
                    (self.REQUIRED_PARAM_ENTERPRISE_NAME, bool(enterprise_name)),
                ])
            )
        return email, enterprise_name, number_of_codes, notes

    def get_missing_params_message(self, parameter_state):
        """
        Get a user-friendly message indicating a missing parameter for the API endpoint.
        """
        params = ', '.join(name for name, present in parameter_state if not present)
        return self.MISSING_REQUIRED_PARAMS_MSG.format(params)

    @permission_required('enterprise.can_access_admin_dashboard')
    def post(self, request):
        """
        POST /enterprise/api/v1/request_codes

        Requires a JSON object of the following format:
        >>> {
        >>>     "email": "bob@alice.com",
        >>>     "enterprise_name": "IBM",
        >>>     "number_of_codes": "50",
        >>>     "notes": "Help notes for codes request",
        >>> }

        Keys:
        *email*
            Email of the customer who has requested more codes.
        *enterprise_name*
            The name of the enterprise requesting more codes.
        *number_of_codes*
            The number of codes requested.
        *notes*
            Help notes related to codes request.
        """
        try:
            email, enterprise_name, number_of_codes, notes = self.get_required_query_params(request)
        except CodesAPIRequestError as invalid_request:
            return Response({'error': str(invalid_request)}, status=HTTP_400_BAD_REQUEST)

        subject_line = _('Code Management - Request for Codes by {token_enterprise_name}').format(
            token_enterprise_name=enterprise_name
        )
        body_msg = create_message_body(email, enterprise_name, number_of_codes, notes)
        app_config = apps.get_app_config("enterprise")
        from_email_address = app_config.enterprise_integrations_email
        cs_email = app_config.customer_success_email
        data = {
            self.REQUIRED_PARAM_EMAIL: email,
            self.REQUIRED_PARAM_ENTERPRISE_NAME: enterprise_name,
            self.OPTIONAL_PARAM_NUMBER_OF_CODES: number_of_codes,
            self.OPTIONAL_PARAM_NOTES: notes,
        }
        try:
            messages_sent = mail.send_mail(
                subject_line,
                body_msg,
                from_email_address,
                [cs_email],
                fail_silently=False
            )
            LOGGER.info('[Enterprise API] Coupon code request emails sent: %s', messages_sent)
            return Response(data, status=HTTP_200_OK)
        except SMTPException:
            error_message = _(
                '[Enterprise API] Failure in sending e-mail to support.'
                ' SupportEmail: {token_cs_email}, UserEmail: {token_email}, EnterpriseName: {token_enterprise_name}'
            ).format(
                token_cs_email=cs_email,
                token_email=email,
                token_enterprise_name=enterprise_name
            )
            LOGGER.error(error_message)
            return Response(
                {'error': str('Request codes email could not be sent')},
                status=HTTP_500_INTERNAL_SERVER_ERROR
            )


class TableauAuthView(generics.GenericAPIView):
    """
    API to authenticate user with Tableau.
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """
        Get the auth token against logged in user from tableau
        """
        url = settings.TABLEAU_URL + '/trusted'
        enterprise_customer_uuid = get_enterprise_customer_from_user_id(request.user.id)
        # Enterprise customer uuid is being store without hyphens in tableau
        tableau_username = enterprise_customer_uuid.replace('-', '')
        payload = {'username': tableau_username}
        files = []
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.request("POST", url, headers=headers, data=payload, files=files)
        return Response(data=response.text)
