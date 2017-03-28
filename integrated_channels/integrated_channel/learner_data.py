"""
Assist integrated channels with retrieving learner completion data.

Module contains resources for integrated pipelines to retrieve all the
grade and competion data for enrollments belonging to a particular
enterprise customer.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from slumber.exceptions import HttpNotFoundError

from enterprise.lms_api import CourseApiClient, GradesApiClient, CertificatesApiClient
from enterprise.models import EnterpriseCourseEnrollment


LOGGER = getLogger(__name__)


class BaseLearnerExporter(object):
    """
    Base class for exporting learner completion data to integrated channels.
    """

    GRADE_PASSING = 'Pass'
    GRADE_FAILING = 'Fail'
    GRADE_INCOMPLETE = 'In Progress'

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

    def __init__(self, user, plugin_configuration):
        """
        Store the data needed to export the learner data to the integrated channel.

        Arguments:

        * ``user``: User instance with access to the Grades API for the Enterprise Customer's courses.
        * ``plugin_configuration``: EnterpriseCustomerPluginConfiguration instance for the current channel.
        """

        self.user = user
        self.plugin_configuration = plugin_configuration
        self.enterprise_customer = plugin_configuration.enterprise_customer
        self.get_learner_data_record = plugin_configuration.get_learner_data_record

        # The Grades API and Certificates API clients require an OAuth2 access token,
        #  so cache the client to allow the token to be reused.
        self.grades_api = None
        self.certificates_api = None

    def collect_learner_data(self):
        """
        Collect learner data for the ``EnterpriseCustomer`` where data sharing consent is granted.

        Arguments:

        * ``user``: User authorized to fetch grades from the LMS API.

        Yields a learner data object for each enrollment, containing:

        * ``enterprise_enrollment``: ``EnterpriseCourseEnrollment`` object.
        * ``completed_date``: datetime instance containing the course/enrollment completion date; None if not complete.
          "Course completion" occurs for instructor-paced courses when course certificates are issued, and
          for self-paced courses, when the course end date is passed, or when the learner achieves a passing grade.
        * ``grade``: string grade recorded for the learner in the course.
        """

        # Fetch the consenting enrollment data, including the enterprise_customer_user.
        # Order by the course_id, to avoid fetching course API data more than we have to.
        enrollment_queryset = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(
            enterprise_customer_user__enterprise_customer=self.enterprise_customer,
        ).order_by('course_id')

        # Fetch course details from the Course API, and cache between calls.
        course_details = None
        course_api = None

        for enterprise_enrollment in enrollment_queryset:

            # Omit any enrollments where consent has not been granted
            if not enterprise_enrollment.consent_available():
                continue

            course_id = enterprise_enrollment.course_id

            # Fetch course details from Courses API
            if course_details is None or course_details['course_id'] != course_id:
                if course_api is None:
                    course_api = CourseApiClient()
                course_details = course_api.get_course_details(course_id)

            if course_details is None:
                # Course not found, so we have nothing to report.
                LOGGER.error("No course details found for enrollment %d: %s",
                             enterprise_enrollment.pk, course_id)
                continue

            # For instructor-paced courses, let the certificate determine course completion
            if course_details.get('pacing') == 'instructor':
                completed_date, grade, is_passing = self._collect_certificate_data(enterprise_enrollment)

            # For self-paced courses, check the Grades API
            else:
                completed_date, grade, is_passing = self._collect_grades_data(enterprise_enrollment, course_details)

            yield self.get_learner_data_record(
                enterprise_enrollment=enterprise_enrollment,
                completed_date=completed_date,
                grade=grade,
                is_passing=is_passing,
            )

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
            is_passing: Boolean indicating if the grade is a passing grade or not.
        """

        if self.certificates_api is None:
            self.certificates_api = CertificatesApiClient(self.user)

        course_id = enterprise_enrollment.course_id
        username = enterprise_enrollment.enterprise_customer_user.user.username

        try:
            certificate = self.certificates_api.get_course_certificate(course_id, username)
            completed_date = certificate.get('created_date')
            if completed_date:
                completed_date = parse_datetime(completed_date)
            else:
                completed_date = timezone.now()

            # For consistency with _collect_grades_data, we only care about Pass/Fail grades. This could change.
            is_passing = certificate.get('is_passing')
            grade = self.grade_passing if is_passing else self.grade_failing

        except HttpNotFoundError:
            completed_date = None
            grade = self.grade_incomplete
            is_passing = False

        return completed_date, grade, is_passing

    def _collect_grades_data(self, enterprise_enrollment, course_details):
        """
        Collect the learner completion data from the Grades API.

        Used for self-paced courses.

        Args:
            enterprise_enrollment (EnterpriseCourseEnrollment): the enterprise enrollment record for which we need to
            collect completion/grade data
            course_details (dict): the course details for the course in the enterprise enrollment record.

        Returns:
            completed_date: Date the course was completed, this is None if course has not been completed.
            grade: Current grade in the course.
            is_passing: Boolean indicating if the grade is a passing grade or not.
        """
        if self.grades_api is None:
            self.grades_api = GradesApiClient(self.user)

        course_id = enterprise_enrollment.course_id
        username = enterprise_enrollment.enterprise_customer_user.user.username

        try:
            grades_data = self.grades_api.get_course_grade(course_id, username)

        except HttpNotFoundError:
            # Grade not found, so we have nothing to report.
            LOGGER.error("No grades data found for %d: %s, %s", enterprise_enrollment.pk, course_id, username)
            return None, None, None

        # Prepare to process the course end date and pass/fail grade
        course_end_date = course_details.get('end')
        if course_end_date is not None:
            course_end_date = parse_datetime(course_end_date)
        now = timezone.now()
        is_passing = grades_data.get('passed')

        # We can consider a course complete if:
        # * the course's end date has passed
        if course_end_date is not None and course_end_date < now:
            completed_date = course_end_date
            grade = self.grade_passing if is_passing else self.grade_failing

        # * Or, the learner has a passing grade (as of now)
        elif is_passing:
            completed_date = now
            grade = self.grade_passing

        # Otherwise, the course is still in progress
        else:
            completed_date = None
            grade = self.grade_incomplete

        return completed_date, grade, is_passing
