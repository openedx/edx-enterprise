# -*- coding: utf-8 -*-
"""
Assist integrated channels with retrieving learner completion data.

Module contains resources for integrated pipelines to retrieve all the
grade and completion data for enrollments belonging to a particular
enterprise customer.
"""

from http import HTTPStatus
from logging import getLogger

from opaque_keys import InvalidKeyError
from slumber.exceptions import HttpNotFoundError

from django.apps import apps
from django.contrib import auth
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from integrated_channels.exceptions import ClientError

try:
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
except ImportError:
    CourseOverview = None
from consent.models import DataSharingConsent
from enterprise.api_client.lms import GradesApiClient
from enterprise.models import EnterpriseCourseEnrollment
from integrated_channels.catalog_service_utils import get_course_id_for_enrollment
from integrated_channels.integrated_channel.exporters import Exporter
from integrated_channels.lms_utils import (
    get_completion_summary,
    get_course_certificate,
    get_course_details,
    get_single_user_grade,
)
from integrated_channels.utils import (
    generate_formatted_log,
    is_already_transmitted,
    is_course_completed,
    parse_datetime_to_epoch_millis,
)

LOGGER = getLogger(__name__)
User = auth.get_user_model()


class LearnerExporter(Exporter):
    """
    Base class for exporting learner completion data to integrated channels.
    """

    GRADE_AUDIT = 'Audit'
    GRADE_PASSING = 'Pass'
    GRADE_FAILING = 'Fail'
    GRADE_INCOMPLETE = 'In Progress'

    def __init__(self, user, enterprise_configuration):
        """
        Store the data needed to export the learner data to the integrated channel.

        Arguments:

        * ``user``: User instance with access to the Grades API for the Enterprise Customer's courses.
        * ``enterprise_configuration``: EnterpriseCustomerPluginConfiguration instance for the current channel.
        """
        # The Grades API and Certificates API clients require an OAuth2 access token,
        # so cache the client to allow the token to be reused. Cache other clients for
        # general reuse.
        self.grades_api = None
        self.certificates_api = None
        self.course_api = None
        self.course_enrollment_api = None

        super().__init__(user, enterprise_configuration)

    @property
    def grade_passing(self):
        """
        Returns the string used for a passing grade.
        """
        return self.GRADE_PASSING

    @property
    def grade_failing(self):
        """
        Returns the string used for a failing grade.
        """
        return self.GRADE_FAILING

    @property
    def grade_incomplete(self):
        """
        Returns the string used for an incomplete course grade.
        """
        return self.GRADE_INCOMPLETE

    @property
    def grade_audit(self):
        """
        Returns the string used for an audit course grade.
        """
        return self.GRADE_AUDIT

    def bulk_assessment_level_export(self):
        """
        Collect assessment level learner data for the ``EnterpriseCustomer`` where data sharing consent is granted.

        Yields a ``LearnerDataTransmissionAudit`` for each subsection in a course under an enrollment, containing:

        * ``enterprise_course_enrollment_id``: The id reference to the ``EnterpriseCourseEnrollment`` object.
        * ``course_id``: The string ID of the course under the enterprise enrollment.
        * ``subsection_id``: The string ID of the subsection within the course.
        * ``grade``: string grade recorded for the learner in the course.
        """
        enrollment_queryset = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
            enterprise_customer_user__active=True,
        ).order_by('course_id')

        # Create a record of each subsection from every enterprise enrollment
        for enterprise_enrollment in enrollment_queryset:
            if not LearnerExporter.has_data_sharing_consent(enterprise_enrollment):
                continue

            assessment_grade_data = self._collect_assessment_grades_data(enterprise_enrollment)

            records = self.get_learner_assessment_data_records(
                enterprise_enrollment=enterprise_enrollment,
                assessment_grade_data=assessment_grade_data,
            )
            if records:
                # There are some cases where we won't receive a record from the above
                # method; right now, that should only happen if we have an Enterprise-linked
                # user for the integrated channel, and transmission of that user's
                # data requires an upstream user identifier that we don't have (due to a
                # failure of SSO or similar). In such a case, `get_learner_data_record`
                # would return None, and we'd simply skip yielding it here.
                for record in records:
                    yield record

    def single_assessment_level_export(self, **kwargs):
        """
        Collect an assessment level learner data for the ``EnterpriseCustomer`` where data sharing consent is
        granted.

        Yields a ``LearnerDataTransmissionAudit`` for each subsection of the course that the learner is enrolled in,
        containing:

        * ``enterprise_course_enrollment_id``: The id reference to the ``EnterpriseCourseEnrollment`` object.
        * ``course_id``: The string ID of the course under the enterprise enrollment.
        * ``subsection_id``: The string ID of the subsection within the course.
        * ``grade``: string grade recorded for the learner in the course.
        * ``learner_to_transmit``: REQUIRED User object, representing the learner whose data is being exported.

        """
        channel = kwargs.get('channel_name', '<channel>')
        lms_user_for_filter = kwargs.get('learner_to_transmit')
        TransmissionAudit = kwargs.get('TransmissionAudit', None)
        course_run_id = kwargs.get('course_run_id', None)
        grade = kwargs.get('grade', None)
        subsection_id = kwargs.get('subsection_id')
        enrollment_queryset = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(
            enterprise_customer_user__active=True,
            enterprise_customer_user__user_id=lms_user_for_filter.id,
            course_id=course_run_id,
        ).order_by('course_id')

        # We are transmitting for an enrollment, so grab just the one.
        enterprise_enrollment = enrollment_queryset.first()

        if not enterprise_enrollment:
            raise ClientError(generate_formatted_log(
                channel,
                self.enterprise_customer.uuid,
                lms_user_for_filter.id,
                course_run_id,
                f'No enterprise_enrollment found, cannot transmit this grade data for subsection {subsection_id}',
            ), HTTPStatus.NOT_FOUND.value)

        already_transmitted = is_already_transmitted(
            TransmissionAudit,
            enterprise_enrollment.id,
            grade,
            subsection_id
        )

        if not (TransmissionAudit and already_transmitted) and LearnerExporter.has_data_sharing_consent(
                enterprise_enrollment):

            assessment_grade_data = self._collect_assessment_grades_data(enterprise_enrollment)

            records = self.get_learner_assessment_data_records(
                enterprise_enrollment=enterprise_enrollment,
                assessment_grade_data=assessment_grade_data,
            )
            if records:
                # There are some cases where we won't receive a record from the above
                # method; right now, that should only happen if we have an Enterprise-linked
                # user for the integrated channel, and transmission of that user's
                # data requires an upstream user identifier that we don't have (due to a
                # failure of SSO or similar). In such a case, `get_learner_data_record`
                # would return None, and we'd simply skip yielding it here.
                for record in records:
                    yield record

    @staticmethod
    def has_data_sharing_consent(enterprise_enrollment):
        """
        Helper method to determine whether an enrollment has data sharing consent or not.
        """
        consent = DataSharingConsent.objects.proxied_get(
            username=enterprise_enrollment.enterprise_customer_user.username,
            course_id=enterprise_enrollment.course_id,
            enterprise_customer=enterprise_enrollment.enterprise_customer_user.enterprise_customer
        )
        if consent.granted and not enterprise_enrollment.audit_reporting_disabled:
            return True

        return False

    def _determine_enrollments_permitted(
            self,
            lms_user_for_filter,
            course_run_id,
            channel_name,
            skip_transmitted,
            TransmissionAudit,
            grade,
    ):
        """
        Determines which enrollments can be safely transmitted after checking
        * enrollments that are already transmitted
        * enrollments that are permitted to be transmitted by selecting enrollments for which:
        *    - data sharing consent is granted
        *    - audit_reporting is enabled (via enterprise level switch)
        """
        enrollments_to_process = self.get_enrollments_to_process(
            lms_user_for_filter,
            course_run_id,
            channel_name,
        )

        if TransmissionAudit and skip_transmitted:
            untransmitted_enrollments = self._filter_out_pre_transmitted_enrollments(
                enrollments_to_process,
                channel_name,
                grade,
                TransmissionAudit
            )
        else:
            untransmitted_enrollments = enrollments_to_process

        # filter out enrollments which don't allow integrated_channels grade transmit
        enrollments_permitted = set()
        for enrollment in untransmitted_enrollments:
            if (not LearnerExporter.has_data_sharing_consent(enrollment) or
                    enrollment.audit_reporting_disabled):
                continue
            enrollments_permitted.add(enrollment)
        return enrollments_permitted

    def export_unique_courses(self):
        """
        Retrieve and export all unique course ID's from an enterprise customer's learner enrollments.
        """
        enrollment_queryset = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
            enterprise_customer_user__active=True,
        ).order_by('course_id')
        return set(get_course_id_for_enrollment(enrollment) for enrollment in enrollment_queryset)

    def get_grades_summary(
        self,
        course_details,
        enterprise_enrollment,
        channel_name,
        incomplete_count=None,
    ):
        '''
        Fetch grades info using either certificate api, or grades api.
        Note: This logic is going to be refactored, so that audit enrollments are treated separately
        - For audit enrollments, currently will fetch using grades api,
        - For non audit, it still calls grades api if pacing !=instructor otherwise calls certificate api
        This pacing logic needs cleanup for a more accurate piece of logic since pacing should not be relevant

        Returns: tuple with values:
            completed_date_from_api, grade_from_api, is_passing_from_api, grade_percent
        '''
        is_audit_enrollment = enterprise_enrollment.is_audit_enrollment
        lms_user_id = enterprise_enrollment.enterprise_customer_user.user_id
        enterprise_customer_uuid = enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid
        course_id = enterprise_enrollment.course_id

        # For instructor-paced and non-audit courses, let the certificate determine course completion
        if course_details.pacing == 'instructor' and not is_audit_enrollment:
            completed_date_from_api, grade_from_api, is_passing_from_api, grade_percent = \
                self._collect_certificate_data(enterprise_enrollment, channel_name)
            LOGGER.info(generate_formatted_log(
                channel_name, enterprise_customer_uuid, lms_user_id, course_id,
                f'_collect_certificate_data finished with CompletedDate: {completed_date_from_api},'
                f' Grade: {grade_from_api}, IsPassing: {is_passing_from_api},'
            ))
        # For self-paced courses, check the Grades API
        else:
            completed_date_from_api, grade_from_api, is_passing_from_api, grade_percent = \
                self.collect_grades_data(enterprise_enrollment, course_details, channel_name)
            LOGGER.info(generate_formatted_log(
                channel_name, enterprise_customer_uuid, lms_user_id, course_id,
                f'_collect_grades_data finished with: CourseMode: {enterprise_enrollment.mode}, '
                f' CompletedDate: {completed_date_from_api},'
                f' Grade: {grade_from_api},'
                f' IsPassing: {is_passing_from_api},'
                f' Audit Mode?: {is_audit_enrollment}'
            ))

        # there is a case for audit enrollment, we are reporting completion based on
        # content count cmopleted, so we may not get a completed_date_from_api
        # and the model requires a completed_date field
        if incomplete_count == 0 and enterprise_enrollment.is_audit_enrollment and completed_date_from_api is None:
            LOGGER.info(generate_formatted_log(
                channel_name, enterprise_customer_uuid, lms_user_id, course_id,
                'Setting completed_date to now() for audit course with all non-gated content done.'
            ))
            completed_date_from_api = timezone.now()

        return completed_date_from_api, grade_from_api, is_passing_from_api, grade_percent

    def get_incomplete_content_count(self, enterprise_enrollment, channel_name):
        '''
        Fetch incomplete content count using completion blocks LMS api
        Will return None for non audit enrollment (but this does not have to be the case necessarily)
        '''
        incomplete_count = None
        is_audit_enrollment = enterprise_enrollment.is_audit_enrollment

        # The decision to not get incomplete count for non audit enrollments can be questioned
        # Right now we don't use this number for non audit. But this condition can be just removed
        # if we decide we need this for non audit enrollments too
        if not is_audit_enrollment:
            return incomplete_count
        lms_user_id = enterprise_enrollment.enterprise_customer_user.user_id
        enterprise_customer_uuid = enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid
        course_id = enterprise_enrollment.course_id

        user = User.objects.get(pk=lms_user_id)
        completion_summary = get_completion_summary(course_id, user)
        incomplete_count = completion_summary.get('incomplete_count')
        LOGGER.info(
            generate_formatted_log(
                channel_name, enterprise_customer_uuid, lms_user_id, course_id,
                f'Incomplete count for audit enrollment is {incomplete_count}'
            ))

        return incomplete_count

    def export(self, **kwargs):
        """
        Collect learner data for the ``EnterpriseCustomer`` where data sharing consent is granted.
        If BOTH learner_to_transmit and course_run_id are present, collected data returned is narrowed to
        that learner and course. If either param is absent or None, ALL data will be collected.

        Yields a learner data object for each enrollment, containing:

        * ``enterprise_enrollment``: ``EnterpriseCourseEnrollment`` object.
        * ``completed_date``: datetime instance containing the course/enrollment completion date; None if not complete.
          "Course completion" occurs for instructor-paced courses when course certificates are issued, and
          for self-paced courses, when the course end date is passed, or when the learner achieves a passing grade.
        * ``grade``: string grade recorded for the learner in the course.
        * ``learner_to_transmit``: OPTIONAL User, filters exported data
        * ``course_run_id``: OPTIONAL Course key string, filters exported data

        """
        channel_name = kwargs.get('app_label')
        lms_user_for_filter = kwargs.get('learner_to_transmit', None)
        course_run_id = kwargs.get('course_run_id', None)
        completed_date = kwargs.get('completed_date', None)
        grade = kwargs.get('grade', None)
        skip_transmitted = kwargs.get('skip_transmitted', True)
        TransmissionAudit = kwargs.get('TransmissionAudit', None)

        # Fetch the consenting enrollment data, including the enterprise_customer_user.
        # Order by the course_id, to avoid fetching course API data more than we have to.
        enrollments_permitted = self._determine_enrollments_permitted(
            lms_user_for_filter,
            course_run_id,
            channel_name,
            skip_transmitted,
            TransmissionAudit,
            grade,
        )
        enrollment_ids_to_export = [enrollment.id for enrollment in enrollments_permitted]

        for enterprise_enrollment in enrollments_permitted:
            lms_user_id = enterprise_enrollment.enterprise_customer_user.user_id
            enterprise_customer_uuid = enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid
            course_id = enterprise_enrollment.course_id

            course_details, error_message = LearnerExporterUtility.get_course_details_by_id(course_id)

            if course_details is None:
                # Course not found, so we have nothing to report.
                LOGGER.error(generate_formatted_log(
                    channel_name, enterprise_customer_uuid, lms_user_id, course_id,
                    f'get_course_details returned None for EnterpriseCourseEnrollment {enterprise_enrollment.pk}'
                    f', error_message: {error_message}'
                ))
                continue

            # For audit courses, check if 100% completed
            # which we define as: no non-gated content is remaining
            incomplete_count = self.get_incomplete_content_count(enterprise_enrollment, channel_name)

            completed_date_from_api, grade_from_api, is_passing_from_api, grade_percent = self.get_grades_summary(
                course_details,
                enterprise_enrollment,
                channel_name,
                incomplete_count,
            )

            # Apply the Source of Truth for Grades
            records = self.get_learner_data_records(
                enterprise_enrollment=enterprise_enrollment,
                completed_date=completed_date_from_api,
                grade=grade_from_api,
                course_completed=is_course_completed(
                    enterprise_enrollment,
                    completed_date,
                    is_passing_from_api,
                    incomplete_count,
                ),
                grade_percent=grade_percent,
            )

            if records:
                # There are some cases where we won't receive a record from the above
                # method; right now, that should only happen if we have an Enterprise-linked
                # user for the integrated channel, and transmission of that user's
                # data requires an upstream user identifier that we don't have (due to a
                # failure of SSO or similar). In such a case, `get_learner_data_record`
                # would return None, and we'd simply skip yielding it here.
                for record in records:
                    # Because we export a course and course run under the same enrollment, we can only remove the
                    # enrollment from the list of enrollments to export, once.
                    try:
                        enrollment_ids_to_export.pop(enrollment_ids_to_export.index(enterprise_enrollment.id))
                    except ValueError:
                        pass

                    yield record

        LOGGER.info(generate_formatted_log(
            channel_name, None, lms_user_for_filter, course_run_id,
            f'export finished. Did not export records for EnterpriseCourseEnrollment objects: '
            f' {enrollment_ids_to_export}.'
        ))

    def _filter_out_pre_transmitted_enrollments(
            self,
            enrollments_to_process,
            channel_name,
            grade,
            transmission_audit
    ):
        """
        Given an enrollments_to_process, returns only enrollments that are not already transmitted
        """
        included_enrollments = set()
        for enterprise_enrollment in enrollments_to_process:
            lms_user_id = enterprise_enrollment.enterprise_customer_user.user_id
            enterprise_customer_uuid = enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid
            course_id = enterprise_enrollment.course_id

            if transmission_audit and \
                    is_already_transmitted(transmission_audit, enterprise_enrollment.id, grade):
                # We've already sent a completion status for this enrollment
                LOGGER.info(generate_formatted_log(
                    channel_name, enterprise_customer_uuid, lms_user_id, course_id,
                    'Skipping export of previously sent enterprise enrollment. '
                    'EnterpriseCourseEnrollment: {enterprise_enrollment_id}'.format(
                        enterprise_enrollment_id=enterprise_enrollment.id
                    )))
                continue
            included_enrollments.add(enterprise_enrollment)
        return included_enrollments

    def get_enrollments_to_process(self, lms_user_for_filter, course_run_id, channel_name):
        """
        Fetches list of EnterpriseCourseEnrollments ordered by course_id.
        List is filtered by learner and course_run_id if both are provided

        lms_user_for_filter: If None, data for ALL courses and learners will be returned
        course_run_id: If None, data for ALL courses and learners will be returned

        """
        enrollment_queryset = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
            enterprise_customer_user__active=True,
        )
        if lms_user_for_filter and course_run_id:
            enrollment_queryset = enrollment_queryset.filter(
                course_id=course_run_id,
                enterprise_customer_user__user_id=lms_user_for_filter.id,
            )
            LOGGER.info(generate_formatted_log(
                channel_name, self.enterprise_customer.uuid, lms_user_for_filter, course_run_id,
                'get_enrollments_to_process run for single learner and course.'))
        enrollment_queryset = enrollment_queryset.order_by('course_id')
        # return resolved list instead of queryset
        return list(enrollment_queryset)

    def get_learner_assessment_data_records(
            self,
            enterprise_enrollment,
            assessment_grade_data
    ):
        """
        Generate a learner assessment data transmission audit with fields properly filled in.
        Returns a list of LearnerDataTransmissionAudit objects.

        enterprise_enrollment: the ``EnterpriseCourseEnrollment`` object we are getting a learner's data for.
        assessment_grade_data: A dict with keys corresponding to different edX course subsections.
        See _collect_assessment_grades_data for the formatted data returned as the value for a given key.
        """
        LearnerDataTransmissionAudit = apps.get_model('integrated_channel', 'LearnerDataTransmissionAudit')
        user_subsection_audits = []
        # Create an audit for each of the subsections in the course data.
        for subsection_data in assessment_grade_data.values():
            subsection_percent_grade = subsection_data.get('grade')
            subsection_id = subsection_data.get('subsection_id')
            # Sanity check for a grade to report
            if not subsection_percent_grade or not subsection_id:
                continue

            user_subsection_audits.append(LearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                course_id=enterprise_enrollment.course_id,
                subsection_id=subsection_id,
                grade=subsection_percent_grade,
            ))

        return user_subsection_audits

    def get_learner_data_records(
            self,
            enterprise_enrollment,
            completed_date=None,
            grade=None,
            course_completed=False,
            grade_percent=None,
    ):  # pylint: disable=unused-argument
        """
        Generate a learner data transmission audit with fields properly filled in.
        """
        LearnerDataTransmissionAudit = apps.get_model('integrated_channel', 'LearnerDataTransmissionAudit')
        completed_timestamp = None
        if completed_date is not None:
            completed_timestamp = parse_datetime_to_epoch_millis(completed_date)

        return [
            LearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                course_id=enterprise_enrollment.course_id,
                course_completed=course_completed,
                completed_timestamp=completed_timestamp,
                grade=grade,
            )
        ]

    def _collect_certificate_data(self, enterprise_enrollment, channel_name):
        """
        Collect the learner completion data from the course certificate.

        Used for Instructor-paced courses.

        If no certificate is found, then returns the completed_date = None, grade = In Progress, on the idea that a
        certificate will eventually be generated.

        Args:
            enterprise_enrollment (EnterpriseCourseEnrollment): the enterprise enrollment record for which we need to
            collect completion/grade data,
            channel_name: labeled for relevant integrated channel this is being called for to enhance logging.

        Returns:
            completed_date: Date the course was completed, this is None if course has not been completed.
            grade: Current grade in the course.
            percent_grade: The current percent grade in the course.
            is_passing: Boolean indicating if the grade is a passing grade or not.
        """

        course_id = enterprise_enrollment.course_id
        lms_user_id = enterprise_enrollment.enterprise_customer_user.user_id
        enterprise_customer_uuid = enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid
        user = User.objects.get(pk=lms_user_id)

        completed_date = None
        grade = self.grade_incomplete
        is_passing = False
        percent_grade = None

        try:
            certificate = get_course_certificate(course_id, user)
        except InvalidKeyError:
            certificate = None
            LOGGER.error(generate_formatted_log(
                channel_name, enterprise_customer_uuid, lms_user_id, course_id,
                'get_course_certificate failed. Certificate fetch failed due to invalid course_id for'
                f' EnterpriseCourseEnrollment: {enterprise_enrollment}. Data export will continue without grade.'
            ))

        if not certificate:
            return completed_date, grade, is_passing, percent_grade

        completed_date = certificate.get('created_date')
        if completed_date:
            completed_date = parse_datetime(completed_date)
        else:
            completed_date = timezone.now()

        # For consistency with _collect_grades_data, we only care about Pass/Fail grades. This could change.
        is_passing = certificate.get('is_passing')
        percent_grade = certificate.get('grade')
        grade = self.grade_passing if is_passing else self.grade_failing

        return completed_date, grade, is_passing, percent_grade

    def _collect_assessment_grades_data(self, enterprise_enrollment):
        """
        Collect a learner's assessment level grade data using an enterprise enrollment, from the Grades API.

        Args:
            enterprise_enrollment (EnterpriseCourseEnrollment): the enterprise enrollment record for which we need to
            collect subsection grades data
        Returns:
            Dict:
                {
                    [subsection name]: {
                        'grade_category': category,
                        'grade': percent grade,
                        'assessment_label': label,
                        'grade_point_score': points earned on the assignment,
                        'grade_points_possible': max possible points on the assignment,
                        'subsection_id': subsection module ID
                    }

                    ...
                }
        """
        if self.grades_api is None:
            self.grades_api = GradesApiClient(self.user)

        course_id = enterprise_enrollment.course_id
        username = enterprise_enrollment.enterprise_customer_user.user.username
        try:
            assessment_grades_data = self.grades_api.get_course_assessment_grades(course_id, username)
        except HttpNotFoundError:
            return {}

        assessment_grades = {}
        for grade in assessment_grades_data:
            if not grade.get('attempted'):
                continue
            assessment_grades[grade.get('subsection_name')] = {
                'grade_category': grade.get('category'),
                'grade': grade.get('percent'),
                'assessment_label': grade.get('label'),
                'grade_point_score': grade.get('score_earned'),
                'grade_points_possible': grade.get('score_possible'),
                'subsection_id': grade.get('module_id')
            }

        return assessment_grades

    def collect_grades_data(self, enterprise_enrollment, course_details, channel_name):
        """
        Collect the learner completion data from the Grades API.

        Used for self-paced courses.

        Args:
            enterprise_enrollment (EnterpriseCourseEnrollment): the enterprise enrollment record for which we need to
            collect completion/grade data
            course_details (CourseOverview): the course details for the course in the enterprise enrollment record.
            channel_name: Integrated channel name for improved logging.

        Returns:
            completed_date: Date the course was completed, None if course has not been completed.
            grade: Current grade in the course.
            is_passing: Boolean indicating if the grade is a passing grade or not.
            percent_grade: a number between 0 and 100
        """

        course_id = enterprise_enrollment.course_id
        lms_user_id = enterprise_enrollment.enterprise_customer_user.user_id
        user = User.objects.get(pk=lms_user_id)
        enterprise_customer_uuid = enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid

        grades_data = get_single_user_grade(course_id, user)

        if grades_data is None:
            LOGGER.error(generate_formatted_log(
                channel_name, enterprise_customer_uuid, lms_user_id, course_id,
                'get_single_user_grade failed. Grades data not found for'
                '  EnterpriseCourseEnrollment: {enterprise_enrollment}.'
                .format(
                    enterprise_enrollment=enterprise_enrollment,
                )))
            return None, None, None, None

        # Prepare to process the course end date and pass/fail grade
        course_end_date = course_details.end
        now = timezone.now()
        is_passing = grades_data.passed

        # We can consider a course complete if:
        # * the course's end date has passed
        if course_end_date is not None and course_end_date < now:
            completed_date = course_end_date
            grade = self.grade_passing if is_passing else self.grade_failing
            grade = self.grade_audit if enterprise_enrollment.is_audit_enrollment else grade

        # * Or, the learner has a passing grade (as of now)
        elif is_passing:
            completed_date = now
            grade = self.grade_passing

        # Otherwise, the course is still in progress
        else:
            completed_date = None
            grade = self.grade_incomplete

        percent_grade = grades_data.percent

        return completed_date, grade, is_passing, percent_grade


class LearnerExporterUtility:
    """ Utility class namespace for accessing Django objects in a common way. """

    @staticmethod
    def lms_user_id_for_ent_course_enrollment_id(enterprise_course_enrollment_id):
        """ Returns the ID of the LMS User for the EnterpriseCourseEnrollment id passed in
        or None if EnterpriseCourseEnrollment not found """
        try:
            return EnterpriseCourseEnrollment.objects.get(
                id=enterprise_course_enrollment_id).enterprise_customer_user.user_id
        except EnterpriseCourseEnrollment.DoesNotExist:
            return None

    @staticmethod
    def get_course_details_by_id(course_id):
        '''
        Convenience method to fetch course details or None (if not found)
        '''
        course_details = None
        error_message = None
        try:
            course_details = get_course_details(course_id)
        except (InvalidKeyError, CourseOverview.DoesNotExist):
            error_message = f'get_course_details failed for course_id {course_id}'

        return course_details, error_message
