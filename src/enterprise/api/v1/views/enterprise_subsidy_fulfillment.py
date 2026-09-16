"""
Views for the Enterprise Subsidy Fulfillment API.
"""

from edx_rbac.decorators import permission_required
from edx_rbac.mixins import PermissionRequiredMixin
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseWrapperApiViewSet
from enterprise.logging import getEnterpriseLogger
from enterprise.utils import NotConnectedToOpenEdX, get_request_value
from enterprise_learner_portal.utils import CourseRunProgressStatuses, get_course_run_status

try:
    from common.djangoapps.course_modes.models import CourseMode
    from common.djangoapps.student.models import CourseEnrollment
    from lms.djangoapps.certificates.api import get_certificate_for_user
    from openedx.core.djangoapps.content.course_overviews.api import get_course_overviews
    from openedx.core.djangoapps.enrollments import api as enrollment_api
except ImportError:
    get_course_overviews = None
    get_certificate_for_user = None
    CourseEnrollment = None
    CourseMode = None
    enrollment_api = None

LOGGER = getEnterpriseLogger(__name__)


class EnrollmentModificationException(Exception):
    """
    An exception that represents an error when modifying the state
    of an enrollment via the EnrollmentApiClient.
    """


class EnterpriseSubsidyFulfillmentViewSet(PermissionRequiredMixin, EnterpriseWrapperApiViewSet):
    """
    General API views for subsidized enterprise course enrollments.

    Supported operations:
        * Fetch a subsidy fulfillment record by uuid.
            /enterprise/api/v1/enterprise-subsidy-fulfillment/{fulfillment_source_uuid}/
        * Cancel a subsidy fulfillment enrollment record by uuid.
            /enterprise/api/v1/enterprise-subsidy-fulfillment/{fulfillment_source_uuid}/cancel-fulfillment/
        * Fetch all unenrolled subsidy fulfillment records.
            /enterprise/api/v1/operator/enterprise-subsidy-fulfillment/unenrolled/

    Cancel and fetch endpoints require a fulfillment source uuid query parameter. Fetching unenrollments supports
    an optional ``unenrolled_after`` query parameter to filter the returned queryset down to only enterprise
    enrollments unenrolled after the supplied datetime.

    Arguments (Fetch & Cancel):
        fulfillment_source_uuid (str): The uuid of the subsidy fulfillment record.

    Arguments (Unenrolled):
        unenrolled_after (str): A datetime string. Only return enrollments unenrolled after this time.

    Returns (Fetch):
        (Response): JSON response containing the subsidy fulfillment record.

    Returns (Unenrolled):
        (Response): JSON list response containing the unenrolled subsidy fulfillment records.

        .. code-block::

            api_response = [
                {
                    enterprise_course_enrollment: {
                        enterprise_customer_user: <user_id>,
                        course_id: <course_id>,
                        unenrolled: <datetime>
                        created: <datetime>
                    }
                    license_uuid/transaction_id: <uuid>,
                    uuid: <uuid>,
                },
            ]

    Raises
        (Http404): If the subsidy fulfillment record does not exist or if subsidy fulfillment exists under a separate
        enterprise.
        (Http403): If the requesting user does not have the appropriate permissions.
        (EnrollmentModificationException): If something goes wrong while updating the platform CourseEnrollment object.
    """
    def get_permission_required(self):
        """
        Return specific permission name based on the view being requested
        """
        if self.action == 'unenrolled':
            return ['enterprise.can_manage_enterprise_fulfillments']
        elif self.action == 'retrieve':
            return ['enterprise.can_access_admin_dashboard']
        elif self.action == 'cancel_enrollment':
            return ['enterprise.can_enroll_learners']
        return []

    def get_permission_object(self):
        """
        Depending on the requested view, returns a record identifier to check perms against.
        """
        if self.request.user.is_staff:
            return None

        if self.action in ('retrieve', 'cancel_enrollment'):
            enrollment_record = self.requested_fulfillment_source.enterprise_course_enrollment
            return str(enrollment_record.enterprise_customer_user.enterprise_customer.uuid)
        else:
            return None

    @cached_property
    def requested_fulfillment_source(self):
        """
        Computes and caches the requested fulfillment source record for this request.
        """
        return self._get_single_fulfillment_by_uuid()

    def _get_single_fulfillment_by_uuid(self):
        """
        Returns a single LearnerCreditCourseEnrollment or LicensedCourseEnrollment associated
        with the requested ``fulfillment_source_uuid``.

        Raises: a 404 if no such record can be found.
        """
        fulfillment_source_uuid = self.kwargs.get('fulfillment_source_uuid')

        # Get learner credit fulfillments under the supplied fulfillment source uuid.
        learner_credit_enrollment = models.LearnerCreditEnterpriseCourseEnrollment.objects.filter(
            uuid=fulfillment_source_uuid,
        ).first()
        if learner_credit_enrollment:
            return learner_credit_enrollment

        # If no LC fulfillment records, look for licensed enrollment records.
        licensed_enrollment = models.LicensedEnterpriseCourseEnrollment.objects.filter(
            uuid=fulfillment_source_uuid,
        ).first()
        if licensed_enrollment:
            return licensed_enrollment

        raise Http404('No fulfillment record matches the provided UUID.')

    def get_subsidy_fulfillment_serializer_class(self):
        """
        Fetch the correct serializer class based on the subsidy type.
        """
        fulfillment_source_uuid = self.kwargs.get('fulfillment_source_uuid')

        learner_credit_enrollments = models.LearnerCreditEnterpriseCourseEnrollment.objects.filter(
            uuid=fulfillment_source_uuid
        )
        if len(learner_credit_enrollments):
            return serializers.LearnerCreditEnterpriseCourseEnrollmentReadOnlySerializer
        licensed_enrollments = models.LicensedEnterpriseCourseEnrollment.objects.filter(
            uuid=fulfillment_source_uuid
        )
        if len(licensed_enrollments):
            return serializers.LicensedEnterpriseCourseEnrollmentReadOnlySerializer

        raise ValidationError('No enrollment found for the given fulfillment source uuid.', code=HTTP_404_NOT_FOUND)

    def _get_unenrolled_fulfillments(self):
        """
        Return the unenrolled subsidy fulfillment records.

        Optionally reads the "unenrolled_after" query param to return records unenrolled after a specified date.

        Furthermore, filter out fulfillments with active related student.CourseEnrollment records.

        Returns:
          Generator of EnterpriseFulfillmentSource records representing only unenrolled fulfillments.
        """
        # Adding licensed enrollment support for future implementations
        if self.request.query_params.get('retrieve_licensed_enrollments'):
            enrollment_table = models.LicensedEnterpriseCourseEnrollment
        else:
            enrollment_table = models.LearnerCreditEnterpriseCourseEnrollment

        unenrolled_queryset = None
        # Apply a modified filter if one is provided via query params
        if self.request.query_params.get('unenrolled_after'):
            unenrolled_queryset = enrollment_table.objects.filter(
                enterprise_course_enrollment__unenrolled_at__gte=self.request.query_params.get('unenrolled_after')
            )
        else:
            unenrolled_queryset = enrollment_table.objects.filter(
                enterprise_course_enrollment__unenrolled_at__isnull=False,
            )
        # Make sure the related enrollment (if it exists) is not active, and exclude it from the results if so.
        #
        # Note: There's no FK between an enterprise enrollment and course enrollment, and the only way to join them is
        # on two distinct join keys (user_id & course_id). There's no native ORM way to do this join, short of using a
        # raw() SQL query. Therefore, we will just make O(N) SQL queries where N = number of recently unenrolled
        # fulfillments.
        unenrolled_fulfillments = (
            fulfillment for fulfillment in unenrolled_queryset
            if not (
                fulfillment.enterprise_course_enrollment
                and fulfillment.enterprise_course_enrollment.course_enrollment
                and fulfillment.enterprise_course_enrollment.course_enrollment.is_active
            )
        )
        return unenrolled_fulfillments

    def get_unenrolled_fulfillment_serializer_class(self):
        """
        Fetch the correct recently unenrolled serializer class based on provided querysets.
        """
        if self.request.query_params.get('retrieve_licensed_enrollments'):
            return serializers.LicensedEnterpriseCourseEnrollmentReadOnlySerializer
        else:
            return serializers.LearnerCreditEnterpriseCourseEnrollmentReadOnlySerializer

    @action(methods=['GET'], detail=False)
    def unenrolled(self, request, *args, **kwargs):
        """
        List all unenrolled subsidy fulfillments.
            /enterprise/api/v1/operator/enterprise-subsidy-fulfillment/unenrolled/

        Args:
            modified (str): A datetime string. Only return enrollments modified after this time.
            retrieve_licensed_enrollments (bool): If true, return data related to licensed enrollments instead of
                learner credit
        """
        LOGGER.warning(
            "[DEPRECATION] This view is deprecated for lack of purpose. Logging to confirm utilization drop-off.",
        )
        queryset = self._get_unenrolled_fulfillments()
        serializer_class = self.get_unenrolled_fulfillment_serializer_class()
        serializer = serializer_class(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, fulfillment_source_uuid, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Retrieve a single subsidized enrollment.
            /enterprise/api/v1/subsidy-fulfillment/{fulfillment_source_uuid}/
        """
        try:
            serializer_class = self.get_subsidy_fulfillment_serializer_class()
            serialized_object = serializer_class(self.requested_fulfillment_source)
        except ValidationError as exc:
            return Response(
                status=HTTP_404_NOT_FOUND,
                data={'detail': exc.detail}
            )
        return Response(serialized_object.data)

    @action(methods=['post'], detail=True)
    def cancel_enrollment(self, request, fulfillment_source_uuid):  # pylint: disable=unused-argument
        """
        Cancel a single subsidized enrollment. Assumes fulfillment source has a valid enterprise enrollment.
        /enterprise/api/v1/enterprise-subsidy-fulfillment/{fulfillment_source_uuid}/cancel-fulfillment/
        """
        try:
            subsidy_fulfillment = self.requested_fulfillment_source
            if subsidy_fulfillment.is_revoked:
                return Response(
                    status=HTTP_200_OK,
                    data={'detail': 'Enrollment is already canceled.'}
                )
        except ValidationError as exc:
            return Response(
                status=HTTP_404_NOT_FOUND,
                data={'detail': exc.detail}
            )

        try:
            username = subsidy_fulfillment.enterprise_course_enrollment.enterprise_customer_user.username
            enrollment_api.update_enrollment(
                username,
                subsidy_fulfillment.enterprise_course_enrollment.course_id,
                is_active=False,
            )
            subsidy_fulfillment.revoke()
        except Exception as exc:  # pylint: disable=broad-except
            msg = (
                f'Subsidized enrollment terminations error: unable to unenroll User {username} '
                f'from Course {subsidy_fulfillment.enterprise_course_enrollment.course_id} because: {str(exc)}'
            )
            LOGGER.error(msg)
            return Response(msg, status=HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(status=HTTP_204_NO_CONTENT)


class LicensedEnterpriseCourseEnrollmentViewSet(EnterpriseWrapperApiViewSet):
    """
    API views for the ``licensed-enterprise-course-enrollment`` API endpoint.
    """

    queryset = models.LicensedEnterpriseCourseEnrollment.objects.all()
    serializer_class = serializers.LicensedEnterpriseCourseEnrollmentReadOnlySerializer
    REQ_EXP_LICENSE_UUIDS_PARAM = 'expired_license_uuids'
    OPT_IGNORE_ENROLLMENTS_MODIFIED_AFTER_PARAM = 'ignore_enrollments_modified_after'

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

    def _terminate_enrollment(self, enterprise_enrollment, course_overview):
        """
        Helper method that switches the given enrollment to audit track, or, if
        no audit track exists for the given course, deletes the enrollment.
        Will do nothing if the user has already "completed" the course run.

        Args:
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
                enrollment_api.update_enrollment(
                    username=enterprise_customer_user.username,
                    course_id=course_run_id,
                    mode=audit_mode,
                )
                LOGGER.info(
                    'Enrollment termination: updated LMS enrollment for User {user} and Enterprise {enterprise} '
                    'in Course {course_id} to Course Mode {mode}.'.format(**log_message_kwargs)
                )
                return self.EnrollmentTerminationStatus.MOVED_TO_AUDIT
            except Exception as exc:
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
                enrollment_api.update_enrollment(
                    username=enterprise_customer_user.username,
                    course_id=course_run_id,
                    is_active=False
                )
                LOGGER.info(
                    'Enrollment termination: successfully unenrolled User {user}, in Enterprise {enterprise} '
                    'from Course {course_id} that contains no audit mode.'.format(**log_message_kwargs)
                )
                return self.EnrollmentTerminationStatus.UNENROLLED
            except Exception as exc:
                msg = (
                    'Enrollment termination: unable to unenroll User {user} in Enterprise {enterprise} '
                    'from Course {course_id}  because: {reason}'.format(
                        reason=str(exc),
                        **log_message_kwargs
                    )
                )
                LOGGER.error('{msg}: {exc}'.format(msg=msg, exc=exc))
                raise EnrollmentModificationException(msg) from exc

    def _course_enrollment_modified_at_by_user_and_course_id(self, licensed_enrollments):
        """
        Returns a dict containing the last time a course enrollment was modified.
        The keys are in the form of f'{user_id}{course_id}'.
        """
        enterprise_course_enrollments = [
            licensed_enrollment.enterprise_course_enrollment for licensed_enrollment in licensed_enrollments
        ]
        user_ids = [str(ece.enterprise_customer_user.user_id) for ece in enterprise_course_enrollments]
        course_ids = [str(ece.course_id) for ece in enterprise_course_enrollments]
        course_enrollment_histories = CourseEnrollment.history.filter(
            user_id__in=user_ids,
            course_id__in=course_ids
        ).order_by('-history_date')

        result = {}

        for history in course_enrollment_histories:
            user_id = history.user_id
            course_id = str(history.course_id)
            key = f'{user_id}{course_id}'
            if key not in result:
                result[key] = history.history_date

        return result

    @action(methods=['post'], detail=False)
    @permission_required('enterprise.can_access_admin_dashboard', fn=lambda request: request.data.get('enterprise_id'))
    def license_revoke(self, request, *args, **kwargs):
        """
        Changes the mode for a user's licensed enterprise course enrollments to the "audit" course mode,
        or unenroll the user if no audit mode exists for a given course.

        Will return a response with status 200 if no errors were encountered while modifying the course enrollment,
        or a 422 if any errors were encountered.  The content of the response is of the form::

            {
                'course-v1:puppies': {'success': true, 'message': 'unenrolled'},
                'course-v1:birds': {'success': true, 'message': 'moved to audit'},
                'course-v1:kittens': {'success': true, 'message': 'course already completed'},
                'course-v1:snakes': {'success': false, 'message': 'unenroll_user_from_course returned false'},
                'course-v1:lizards': {'success': false, 'message': 'Some other exception'},
            }

        The first four messages are the values of constants that a client may expect to receive and parse accordingly.
        """
        dependencies = [
            CourseMode, get_certificate_for_user, get_course_overviews, enrollment_api
        ]
        if not all(dependencies):
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

        revocation_results = {}
        any_failures = False
        for course_overview in get_course_overviews(list(enrollments_by_course_id.keys())):
            course_id = str(course_overview.get('id'))
            enterprise_enrollment = enrollments_by_course_id.get(course_id)
            try:
                revocation_status = self._terminate_enrollment(enterprise_enrollment, course_overview)
                revocation_results[course_id] = {'success': True, 'message': revocation_status}
                if revocation_status != self.EnrollmentTerminationStatus.COURSE_COMPLETED:
                    enterprise_enrollment.license.revoke()
            except EnrollmentModificationException as exc:
                revocation_results[course_id] = {'success': False, 'message': str(exc)}
                any_failures = True

        status_code = status.HTTP_200_OK if not any_failures else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(revocation_results, status=status_code)

    @action(methods=['post'], detail=False)
    @permission_required('enterprise.can_enroll_learners')
    def bulk_licensed_enrollments_expiration(self, request):
        """
        Changes the mode for licensed enterprise course enrollments to the "audit" course mode,
        or unenroll the user if no audit mode exists for each expired license uuid

        Args:
            expired_license_uuids: The expired license uuids.
            ignore_enrollments_modified_after: All course enrollments modified past this given date will be ignored,
                                               i.e. the enterprise subscription plan expiration date.
        """

        dependencies = [
            CourseEnrollment, CourseMode, get_certificate_for_user, get_course_overviews, enrollment_api
        ]
        if not all(dependencies):
            raise NotConnectedToOpenEdX(
                _('To use this endpoint, this package must be '
                  'installed in an Open edX environment.')
            )

        expired_license_uuids = get_request_value(request, self.REQ_EXP_LICENSE_UUIDS_PARAM, '')
        ignore_enrollments_modified_after = get_request_value(
            request,
            self.OPT_IGNORE_ENROLLMENTS_MODIFIED_AFTER_PARAM,
            None
        )

        if not expired_license_uuids:
            return Response(
                'Parameter {} must be provided'.format(self.REQ_EXP_LICENSE_UUIDS_PARAM),
                status=status.HTTP_400_BAD_REQUEST
            )

        if ignore_enrollments_modified_after:
            ignore_enrollments_modified_after = parse_datetime(ignore_enrollments_modified_after)
            if not ignore_enrollments_modified_after:
                return Response(
                    'Parameter {} is malformed, please provide a date in ISO-8601 format'.format(
                        self.OPT_IGNORE_ENROLLMENTS_MODIFIED_AFTER_PARAM
                    ),
                    status=status.HTTP_400_BAD_REQUEST
                )

        licensed_enrollments = models.LicensedEnterpriseCourseEnrollment.objects.filter(
            license_uuid__in=expired_license_uuids
        ).select_related('enterprise_course_enrollment')

        course_overviews = get_course_overviews(
            list(licensed_enrollments.values_list('enterprise_course_enrollment__course_id', flat=True))
        )
        indexed_overviews = {overview.get('id'): overview for overview in course_overviews}

        course_enrollment_modified_at_by_user_and_course_id = \
            self._course_enrollment_modified_at_by_user_and_course_id(
                licensed_enrollments
            ) if ignore_enrollments_modified_after else {}

        any_failures = False

        for licensed_enrollment in licensed_enrollments:
            enterprise_course_enrollment = licensed_enrollment.enterprise_course_enrollment
            user_id = enterprise_course_enrollment.enterprise_customer_user.user_id
            course_id = enterprise_course_enrollment.course_id
            course_overview = indexed_overviews.get(course_id)

            if licensed_enrollment.is_revoked:
                LOGGER.info(
                    'Enrollment termination: not updating enrollment in {} for User {} '
                    'licensed enterprise enrollment has already been revoked in the past.'.format(
                        course_id,
                        user_id
                    )
                )
                continue

            if ignore_enrollments_modified_after:
                key = f'{user_id}{course_id}'
                course_enrollment_modified_at = course_enrollment_modified_at_by_user_and_course_id[key]
                if course_enrollment_modified_at >= ignore_enrollments_modified_after:
                    LOGGER.info(
                        'Enrollment termination: not updating enrollment in {} for User {} '
                        'course enrollment has been modified past {}.'.format(
                            course_id,
                            user_id,
                            ignore_enrollments_modified_after
                        )
                    )
                    continue

            try:
                termination_status = self._terminate_enrollment(enterprise_course_enrollment, course_overview)
                license_uuid = enterprise_course_enrollment.license.license_uuid
                LOGGER.info(
                    f"EnterpriseCourseEnrollment record with enterprise license {license_uuid} "
                    f"unenrolled to status {termination_status}."
                )
                if termination_status != self.EnrollmentTerminationStatus.COURSE_COMPLETED:
                    enterprise_course_enrollment.license.revoke()
            except EnrollmentModificationException as exc:
                LOGGER.error(
                    f"Failed to unenroll EnterpriseCourseEnrollment record for enterprise license "
                    f"{enterprise_course_enrollment.license.license_uuid}. error message {str(exc)}."
                )
                any_failures = True

        status_code = status.HTTP_200_OK if not any_failures else status.HTTP_422_UNPROCESSABLE_ENTITY
        return Response(status=status_code)
