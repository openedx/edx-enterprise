# -*- coding: utf-8 -*-
"""
Assist integrated channels with retrieving learner completion data.

Module contains resources for integrated pipelines to retrieve all the
grade and completion data for enrollments belonging to a particular
enterprise customer.
"""

from logging import getLogger

from opaque_keys import InvalidKeyError
from slumber.exceptions import HttpNotFoundError

from django.apps import apps
from django.contrib import auth
from django.utils import timezone
from django.utils.dateparse import parse_datetime

try:
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
except ImportError:
    CourseOverview = None
from consent.models import DataSharingConsent
from enterprise.api_client.lms import GradesApiClient
from enterprise.models import EnterpriseCourseEnrollment
from integrated_channels.integrated_channel.exporters import Exporter
from integrated_channels.lms_utils import get_course_certificate, get_course_details, get_single_user_grade
from integrated_channels.utils import generate_formatted_log, is_already_transmitted, parse_datetime_to_epoch_millis

LOGGER = getLogger(__name__)
User = auth.get_user_model()  # pylint: disable=invalid-name


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

        Yields a learner assessment data object for each subsection within a course under an enrollment, containing:

        * ``enterprise_enrollment``: ``EnterpriseCourseEnrollment`` object.
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
        Collect a single assessment level learner data for the ``EnterpriseCustomer`` where data sharing consent is
        granted.

        Yields a learner assessment data object for each subsection of the course that the learner is enrolled in,
        containing:

        * ``enterprise_enrollment``: ``EnterpriseCourseEnrollment`` object.
        * ``course_id``: The string ID of the course under the enterprise enrollment.
        * ``subsection_id``: The string ID of the subsection within the course.
        * ``grade``: string grade recorded for the learner in the course.
        """
        learner_to_transmit = kwargs.get('learner_to_transmit', None)
        TransmissionAudit = kwargs.get('TransmissionAudit', None)  # pylint: disable=invalid-name
        course_run_id = kwargs.get('course_run_id', None)
        grade = kwargs.get('grade', None)
        subsection_id = kwargs.get('subsection_id')
        enrollment_queryset = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(
            enterprise_customer_user__active=True,
            enterprise_customer_user__user_id=learner_to_transmit.id,
            course_id=course_run_id,
        ).order_by('course_id')

        # We are transmitting for a single enrollment, so grab just the one.
        enterprise_enrollment = enrollment_queryset.first()

        generate_formatted_log(
            'Beginning single exportation of learner data for enrollment: {enrollment}'.format(
                enrollment=enterprise_enrollment.id
            )
        )

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

    def _determine_enrollments_permitted(  # pylint: disable=invalid-name
            self,
            learner_to_transmit,
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
            learner_to_transmit,
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

    def export(self, **kwargs):  # pylint: disable=R0915
        """
        Collect learner data for the ``EnterpriseCustomer`` where data sharing consent is granted.

        Yields a learner data object for each enrollment, containing:

        * ``enterprise_enrollment``: ``EnterpriseCourseEnrollment`` object.
        * ``completed_date``: datetime instance containing the course/enrollment completion date; None if not complete.
          "Course completion" occurs for instructor-paced courses when course certificates are issued, and
          for self-paced courses, when the course end date is passed, or when the learner achieves a passing grade.
        * ``grade``: string grade recorded for the learner in the course.
        """
        channel_name = kwargs.get('app_label')
        learner_to_transmit = kwargs.get('learner_to_transmit', None)
        course_run_id = kwargs.get('course_run_id', None)
        completed_date = kwargs.get('completed_date', None)
        is_passing = kwargs.get('is_passing', False)
        grade = kwargs.get('grade', None)
        skip_transmitted = kwargs.get('skip_transmitted', True)
        TransmissionAudit = kwargs.get('TransmissionAudit', None)  # pylint: disable=invalid-name
        # Fetch the consenting enrollment data, including the enterprise_customer_user.
        # Order by the course_id, to avoid fetching course API data more than we have to.
        generate_formatted_log(
            'Starting Export. CompletedDate: {completed_date}, Course: {course_run}, '
            'Grade: {grade}, IsPassing: {is_passing}, User: {user_id}'.format(
                completed_date=completed_date,
                course_run=course_run_id,
                grade=grade,
                is_passing=is_passing,
                user_id=learner_to_transmit.id if learner_to_transmit else None
            ),
            channel_name=channel_name,
            enterprise_customer_identifier=self.enterprise_customer.name
        )

        enrollments_permitted = self._determine_enrollments_permitted(
            learner_to_transmit,
            course_run_id,
            channel_name,
            skip_transmitted,
            TransmissionAudit,
            grade,
        )
        enrollment_ids_to_export = [enrollment.id for enrollment in enrollments_permitted]
        LearnerExporter._log_beginning_export(
            enrollment_ids_to_export,
            channel_name,
            self.enterprise_customer.name
        )

        for enterprise_enrollment in enrollments_permitted:
            is_audit_enrollment = enterprise_enrollment.is_audit_enrollment
            enterprise_user_id = enterprise_enrollment.enterprise_customer_user.user_id
            course_id = enterprise_enrollment.course_id

            course_details = None
            try:
                course_details = get_course_details(course_id)
                generate_formatted_log(
                    'Currently exporting for course: {curr_course}, '
                    'Course_details: {course_details} '.format(
                        curr_course=course_id,
                        course_details=course_details
                    ),
                    channel_name=channel_name,
                    enterprise_customer_identifier=self.enterprise_customer.name
                )
            except InvalidKeyError:
                LearnerExporter._log_courseid_not_found(course_id, enterprise_enrollment)
            except CourseOverview.DoesNotExist:
                LearnerExporter._log_course_details_not_found(
                    course_run_id,
                )

            if course_details is None:
                # Course not found, so we have nothing to report.
                generate_formatted_log(
                    'Course run details not found. EnterpriseEnrollment: {enterprise_enrollment_pk}, '
                    'Course: {course_id}'.format(
                        enterprise_enrollment_pk=enterprise_enrollment.pk,
                        course_id=course_id
                    ),
                    channel_name=channel_name,
                    enterprise_customer_identifier=self.enterprise_customer.name,
                    is_error=True,
                )
                continue

            # For instructor-paced and non-audit courses, let the certificate determine course completion
            if course_details.pacing == 'instructor' and not is_audit_enrollment:
                completed_date_from_api, grade_from_api, is_passing_from_api, grade_percent = \
                    self._collect_certificate_data(enterprise_enrollment)
                generate_formatted_log(
                    'Received data from certificate api. CompletedDate: {completed_date},'
                    ' Course Id: {course_id},'
                    ' Enterprise: {enterprise}, '
                    ' Grade: {grade}, IsPassing: {is_passing},'
                    ' Learner LMS User Id: {user_id}'.format(
                        completed_date=completed_date_from_api,
                        grade=grade_from_api,
                        is_passing=is_passing_from_api,
                        course_id=course_id,
                        user_id=enterprise_user_id,
                        enterprise=enterprise_enrollment.enterprise_customer_user.enterprise_customer.slug
                    ),
                    channel_name=channel_name,
                    enterprise_customer_identifier=self.enterprise_customer.name
                )
            # For self-paced courses, check the Grades API
            else:
                completed_date_from_api, grade_from_api, is_passing_from_api, grade_percent = \
                    self._collect_grades_data(enterprise_enrollment, course_details, is_audit_enrollment)
                generate_formatted_log(
                    'Received data from grades api.'
                    ' CompletedDate: {completed_date}, Course: {course_id}, '
                    ' Enterprise: {enterprise}, Grade: {grade}, IsPassing: {is_passing},'
                    ' Learner LMS User Id: {user_id}'.format(
                        completed_date=completed_date_from_api,
                        grade=grade_from_api,
                        is_passing=is_passing_from_api,
                        course_id=course_id,
                        user_id=enterprise_user_id,
                        enterprise=enterprise_enrollment.enterprise_customer_user.enterprise_customer.slug
                    ),
                    channel_name=channel_name,
                    enterprise_customer_identifier=self.enterprise_customer.name
                )

            # todo: we need to refactor so single learner is not so mixed in with bulk case
            exporting_single_learner = learner_to_transmit and course_run_id
            if exporting_single_learner and (grade != grade_from_api or is_passing != is_passing_from_api):
                enterprise_user = enterprise_enrollment.enterprise_customer_user
                generate_formatted_log(
                    'Attempt to transmit conflicting data. '
                    ' Course: {course_id}, Enterprise: {enterprise},'
                    ' EnrollmentId: {enrollment_id},'
                    ' Grade: {grade}, GradeAPI: {grade_api}, IsPassing: {is_passing},'
                    ' IsPassingAPI: {is_passing_api}, Learner LMS User Id: {user_id}'.format(
                        grade=grade,
                        is_passing=is_passing,
                        grade_api=grade_from_api,
                        is_passing_api=is_passing_from_api,
                        course_id=course_id,
                        enrollment_id=enterprise_enrollment.id,
                        user_id=enterprise_user.user_id,
                        enterprise=enterprise_user.enterprise_customer.slug
                    ),
                    channel_name=channel_name,
                    enterprise_customer_identifier=self.enterprise_customer.name,
                    is_error=True
                )
            # Apply the Single Source of Truth for Grades
            grade = grade_from_api
            completed_date = completed_date_from_api
            is_passing = is_passing_from_api
            records = self.get_learner_data_records(
                enterprise_enrollment=enterprise_enrollment,
                completed_date=completed_date,
                grade=grade,
                is_passing=is_passing,
                grade_percent=grade_percent
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

        generate_formatted_log(
            'Finished exporting enrollments. Skipped enrollments: {enrollments}.'.format(
                enrollments=enrollment_ids_to_export,
            ),
            channel_name=channel_name,
            enterprise_customer_identifier=self.enterprise_customer.name
        )

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
            if transmission_audit and \
                    is_already_transmitted(transmission_audit, enterprise_enrollment.id, grade):
                # We've already sent a completion status for this enrollment
                generate_formatted_log(
                    'Skipping export of previously sent enterprise enrollment. '
                    'EnterpriseEnrollment: {enterprise_enrollment_id}'.format(
                        enterprise_enrollment_id=enterprise_enrollment.id
                    ),
                    channel_name=channel_name,
                    enterprise_customer_identifier=self.enterprise_customer.name
                )
                continue
            included_enrollments.add(enterprise_enrollment)
        return included_enrollments

    def get_enrollments_to_process(self, learner_to_transmit, course_run_id, channel_name):
        """
        Fetches list of EnterpriseCourseEnrollments ordered by course_id.
        List is filtered by learner and course_run_id if both are provided
        """
        enrollment_queryset = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
            enterprise_customer_user__active=True,
        )
        if learner_to_transmit and course_run_id:
            enrollment_queryset = enrollment_queryset.filter(
                course_id=course_run_id,
                enterprise_customer_user__user_id=learner_to_transmit.id,
            )
            generate_formatted_log(
                'Exporting single learner. Course: {course_run},'
                ' Learner LMS User Id: {user_id}'.format(
                    course_run=course_run_id,
                    user_id=learner_to_transmit.id
                ),
                channel_name=channel_name,
                enterprise_customer_identifier=self.enterprise_customer.name
            )
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
        """
        # pylint: disable=invalid-name
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
            is_passing=False,
            grade_percent=None  # pylint: disable=unused-argument
    ):
        """
        Generate a learner data transmission audit with fields properly filled in.
        """
        # pylint: disable=invalid-name
        LearnerDataTransmissionAudit = apps.get_model('integrated_channel', 'LearnerDataTransmissionAudit')
        completed_timestamp = None
        course_completed = False
        if completed_date is not None:
            completed_timestamp = parse_datetime_to_epoch_millis(completed_date)
            course_completed = is_passing

        return [
            LearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=enterprise_enrollment.id,
                course_id=enterprise_enrollment.course_id,
                course_completed=course_completed,
                completed_timestamp=completed_timestamp,
                grade=grade,
            )
        ]

    def _collect_certificate_data(self, enterprise_enrollment):
        """
        Collect the learner completion data from the course certificate.

        Used for Instructor-paced courses.

        If no certificate is found, then returns the completed_date = None, grade = In Progress, on the idea that a
        certificate will eventually be generated.

        Args:
            enterprise_enrollment (EnterpriseCourseEnrollment): the enterprise enrollment record for which we need to
            collect completion/grade data

        Returns:
            completed_date: Date the course was completed, this is None if course has not been completed.
            grade: Current grade in the course.
            percent_grade: The current percent grade in the course.
            is_passing: Boolean indicating if the grade is a passing grade or not.
        """

        course_id = enterprise_enrollment.course_id
        lms_user_id = enterprise_enrollment.enterprise_customer_user.user_id
        user = User.objects.get(pk=lms_user_id)

        completed_date = None
        grade = self.grade_incomplete
        is_passing = False
        percent_grade = None

        try:
            certificate = get_course_certificate(course_id, user)
        except InvalidKeyError:
            LearnerExporter._log_courseid_not_found(course_id, enterprise_enrollment, lms_user_id)
            return completed_date, grade, is_passing, percent_grade

        if not certificate:
            LearnerExporter._log_cert_not_found(course_id, enterprise_enrollment, lms_user_id)
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

    @staticmethod
    def _log_beginning_export(enrollment_ids_to_export, channel_name, enterprise_customer_name):
        """beginning export of permitted enrollments"""
        generate_formatted_log(
            'Beginning export of enrollments: {enrollments}.'.format(
                enrollments=enrollment_ids_to_export,
            ),
            channel_name=channel_name,
            enterprise_customer_identifier=enterprise_customer_name,
        )

    @staticmethod
    def _log_cert_not_found(course_id, enterprise_enrollment, lms_user_id):
        """
        Standardized logging for no certificate found (refactor candidate)
        """
        LOGGER.error('[Integrated Channel] Certificate not found for user'
                     ' Course: {course_id}, EnterpriseEnrollment: {enterprise_enrollment}, '
                     ' Learner LMS User Id: {user_id}'
                     .format(
                         course_id=course_id,
                         enterprise_enrollment=enterprise_enrollment,
                         user_id=lms_user_id,
                     ))

    @staticmethod
    def _log_courseid_not_found(course_id, enterprise_enrollment, lms_user_id=None):
        """
        Standardized logging for no certificate found  (refactor candidate)
        """
        LOGGER.error('[Integrated Channel] Certificate fetch failed due to invalid course_id'
                     ' Course: {course_id}, EnterpriseEnrollment: {enterprise_enrollment}, '
                     ' Learner LMS User Id: {user_id}'
                     .format(
                         course_id=course_id,
                         enterprise_enrollment=enterprise_enrollment,
                         user_id=lms_user_id,
                     ))

    @staticmethod
    def _log_course_details_not_found(course_id):
        """
        course_id valid but not course details are found
        """
        LOGGER.error('[Integrated Channel] course details not found for '
                     'Course: {course_id}'.format(course_id=course_id))

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

    def _collect_grades_data(self, enterprise_enrollment, course_details, is_audit_enrollment):
        """
        Collect the learner completion data from the Grades API.

        Used for self-paced courses.

        Args:
            enterprise_enrollment (EnterpriseCourseEnrollment): the enterprise enrollment record for which we need to
            collect completion/grade data
            course_details (CourseOverview): the course details for the course in the enterprise enrollment record.

        Returns:
            completed_date: Date the course was completed, None if course has not been completed.
            grade: Current grade in the course.
            is_passing: Boolean indicating if the grade is a passing grade or not.
            percent_grade: a number between 0 and 100
        """

        course_id = enterprise_enrollment.course_id
        lms_user_id = enterprise_enrollment.enterprise_customer_user.user_id
        user = User.objects.get(pk=lms_user_id)

        grades_data = get_single_user_grade(course_id, user)

        if grades_data is None:
            LOGGER.error('[Integrated Channel] Grades data not found.'
                         ' Course: {course_id}, EnterpriseEnrollment: {enterprise_enrollment},'
                         ' Learner LMS User Id: {user_id}'.format(
                             course_id=course_id,
                             user_id=lms_user_id,
                             enterprise_enrollment=enterprise_enrollment.pk))
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
            grade = self.grade_audit if is_audit_enrollment else grade

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
