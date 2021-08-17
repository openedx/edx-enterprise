# -*- coding: utf-8 -*-
"""
Send xAPI statements to the LRS configured via admin.
"""

from logging import getLogger

import six

from django.contrib import auth
from django.core.management.base import BaseCommand, CommandError

from enterprise.api_client.discovery import get_course_catalog_api_service_client
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer, EnterpriseCustomerUser
from enterprise.utils import NotConnectedToOpenEdX
from integrated_channels.xapi.models import XAPILearnerDataTransmissionAudit, XAPILRSConfiguration
from integrated_channels.xapi.utils import is_success_response, send_course_completion_statement

try:
    from lms.djangoapps.grades.models import PersistentCourseGrade
except ImportError:
    PersistentCourseGrade = None

try:
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
except ImportError:
    CourseOverview = None

LOGGER = getLogger(__name__)
User = auth.get_user_model()


class Command(BaseCommand):
    """
    Send course completion xAPI statements to enterprise customers.
    """

    def add_arguments(self, parser):
        """
        Add required arguments to the parser.
        """
        parser.add_argument(
            '--days',
            dest='days',
            required=False,
            type=int,
            default=1,
            help='Send xAPI analytics for learners who enrolled during last this number of days.'
        )
        parser.add_argument(
            '--enterprise_customer_uuid',
            dest='enterprise_customer_uuid',
            type=str,
            required=False,
            help='Send xAPI analytics for this enterprise customer only.'
        )
        super().add_arguments(parser)

    @staticmethod
    def parse_arguments(*args, **options):
        """
        Parse and validate arguments for the command.

        Arguments:
            *args: Positional arguments passed to the command
            **options: Optional arguments passed to the command

        Returns:
            A tuple containing parsed values for
            1. days (int): Integer showing number of days to lookup enterprise enrollments,
                course completion etc and send to xAPI LRS
            2. enterprise_customer_uuid (EnterpriseCustomer): Enterprise Customer if present then
                send xAPI statements just for this enterprise.
        """
        days = options.get('days', 1)
        enterprise_customer_uuid = options.get('enterprise_customer_uuid')
        enterprise_customer = None

        if enterprise_customer_uuid:
            try:
                enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)
            except EnterpriseCustomer.DoesNotExist as no_customer_error:
                raise CommandError('Enterprise customer with uuid "{enterprise_customer_uuid}" does not exist.'.format(
                    enterprise_customer_uuid=enterprise_customer_uuid
                )) from no_customer_error

        return days, enterprise_customer

    def handle(self, *args, **options):
        """
        Send xAPI statements.
        """
        if not all((PersistentCourseGrade, CourseOverview)):
            raise NotConnectedToOpenEdX("This package must be installed in an OpenEdX environment.")

        days, enterprise_customer = self.parse_arguments(*args, **options)

        if enterprise_customer:
            try:
                lrs_configuration = XAPILRSConfiguration.objects.get(
                    active=True,
                    enterprise_customer=enterprise_customer
                )
            except XAPILRSConfiguration.DoesNotExist as no_config_exception:
                raise CommandError('No xAPI Configuration found for "{enterprise_customer}"'.format(
                    enterprise_customer=enterprise_customer.name
                )) from no_config_exception

            # Send xAPI analytics data to the configured LRS
            self.send_xapi_statements(lrs_configuration, days)
        else:
            for lrs_configuration in XAPILRSConfiguration.objects.filter(active=True):
                self.send_xapi_statements(lrs_configuration, days)

    def send_xapi_statements(self, lrs_configuration, days):
        """
        Send xAPI analytics data of the enterprise learners to the given LRS.

        Arguments:
            lrs_configuration (XAPILRSConfiguration): Configuration object containing LRS configurations
                of the LRS where to send xAPI  learner analytics.

            days (Numeric):  Deprecated.  Original implementation utilized a "days" parameter to limit
                the number of enrollments transmitted, but this proved to be more problematic than helpful.
        """
        enterprise_course_enrollments = self.get_enterprise_course_enrollments(lrs_configuration.enterprise_customer)
        enterprise_enrollment_ids = self.get_enterprise_enrollment_ids(enterprise_course_enrollments)
        xapi_transmission_queryset = self.get_xapi_transmission_queryset(enterprise_enrollment_ids)
        pertinent_enrollment_ids = self.get_pertinent_enrollment_ids(xapi_transmission_queryset)
        pertinent_enrollments = self.get_pertinent_enrollments(enterprise_course_enrollments, pertinent_enrollment_ids)
        enrollment_grades = self.get_course_completions(pertinent_enrollments)
        users = self.prefetch_users(enrollment_grades)
        course_overviews = self.prefetch_courses(enrollment_grades)
        course_catalog_client = get_course_catalog_api_service_client(site=lrs_configuration.enterprise_customer.site)

        for xapi_transmission in xapi_transmission_queryset:

            object_type = self.get_object_type(xapi_transmission)

            try:
                course_grade = enrollment_grades[xapi_transmission.enterprise_course_enrollment_id]
            except KeyError:
                continue

            user = users.get(course_grade.user_id)
            courserun_id = six.text_type(course_grade.course_id)
            course_overview = course_overviews.get(course_grade.course_id)
            course_run_identifiers = course_catalog_client.get_course_run_identifiers(courserun_id)
            course_overview.course_key = course_run_identifiers['course_key']
            course_overview.course_uuid = course_run_identifiers['course_uuid']

            default_error_message = 'Days argument has been deprecated.  Value: {days}'.format(days=days)
            response_fields = {'status': 500, 'error_message': default_error_message}
            response_fields = send_course_completion_statement(
                lrs_configuration,
                user,
                course_overview,
                course_grade,
                object_type,
                response_fields
            )

            if is_success_response(response_fields):
                self.save_xapi_learner_data_transmission_audit(
                    xapi_transmission,
                    course_grade.percent_grade,
                    1,
                    course_grade.passed_timestamp,
                    response_fields.get('status'),
                    response_fields.get('error_message')
                )

    @staticmethod
    def get_object_type(xapi_transmission):
        """
        Returns the object type for the xAPI transmission based on the course object identifier
        """
        object_type = 'course'
        if 'course-v1' in xapi_transmission.course_id:
            object_type = 'courserun'
        return object_type

    def get_enterprise_course_enrollments(self, enterprise_customer):
        """
        Retrieves the set of EnterpriseCourseEnrollment records for the specified EnterpriseCustomer
        """
        return EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user_id__enterprise_customer=enterprise_customer
        )

    def get_enterprise_enrollment_ids(self, enterprise_course_enrollments):
        """
        Extracts the identifiers from the provided EnterprsieCourseEnrollment queryset.
        """
        return enterprise_course_enrollments.values_list('id', flat=True)

    @staticmethod
    def get_xapi_transmission_queryset(enterprise_enrollment_ids):
        """
        Retrieves the xAPI transmission records for the specified list of EnterpriseCourseEnrollment identifiers
        """
        return XAPILearnerDataTransmissionAudit.objects.filter(
            enterprise_course_enrollment_id__in=enterprise_enrollment_ids,
            course_completed=0,
        )

    @staticmethod
    def get_pertinent_enrollment_ids(xapi_transmission_queryset):
        """
        Returns the set of enterprise course enrollment identifiers from the
        provided set of xAPI transmission records.
        """
        return xapi_transmission_queryset.values_list('enterprise_course_enrollment_id', flat=True)

    def get_pertinent_enrollments(self, enterprise_course_enrollments, pertinent_enrollment_ids):
        """
        Returns the subset of enterprise course enrollments matching the list of provided identfiers
        """
        return enterprise_course_enrollments.filter(id__in=pertinent_enrollment_ids)

    @staticmethod
    def get_lms_user_id_from_enrollment(enterprise_course_enrollment):
        """
        Retrieves the corresponding User identifier for the specified EnterpriseCourseEnrollment record
        """
        return EnterpriseCustomerUser.objects.get(id=enterprise_course_enrollment.enterprise_customer_user_id).user_id

    @staticmethod
    def get_grade_record_for_enrollment(enterprise_course_enrollment):
        """
        Retrieves the corresponding PersistentCourseGrade record (if available)
        for the specified EnterpriseCourseEnrollment record
        """
        lms_user_id = Command.get_lms_user_id_from_enrollment(enterprise_course_enrollment)
        course_id = enterprise_course_enrollment.course_id
        grade_records = PersistentCourseGrade.objects.filter(
            user_id=lms_user_id,
            course_id=course_id,
            passed_timestamp__isnull=False
        )
        return grade_records.first()

    @staticmethod
    def get_course_completions(enterprise_course_enrollments):
        """
        Get course completions via PersistentCourseGrade for all the learners of given enterprise customer.

        Arguments:
            enterprise_customer (EnterpriseCustomer): Include Course enrollments for learners
                of this enterprise customer.
            days (int): Include course enrollment of this number of days.

        Returns:
            (list): A list of PersistentCourseGrade objects.

        """
        ece_grades = {}
        for ece in enterprise_course_enrollments:
            grade_record = Command.get_grade_record_for_enrollment(ece)
            if grade_record is not None:
                ece_grades.setdefault(ece.id, grade_record)
        return ece_grades

    @staticmethod
    def prefetch_users(enrollment_grades):
        """
        Prefetch Users from the list of user_ids present in the persistent_course_grades.

        Arguments:
            enrollment_grades (list): A list of PersistentCourseGrade.

        Returns:
            (dict): A dictionary containing user_id to user mapping.
        """
        users = User.objects.filter(
            id__in=[grade.user_id for grade in enrollment_grades.values()]
        )
        return {
            user.id: user for user in users
        }

    def prefetch_courses(self, enrollment_grades):
        """
        Prefetch courses from the list of course_ids present in the persistent_course_grades.

        Arguments:
            persistent_course_grades (list): A list of PersistentCourseGrade.

        Returns:
            (dict): A dictionary containing course_id to course_overview mapping.
        """
        return CourseOverview.get_from_ids(
            [grade.course_id for grade in enrollment_grades.values()]
        )

    def save_xapi_learner_data_transmission_audit(self, xapi_transmission,
                                                  course_grade, course_completed, completed_timestamp,
                                                  status, error_message):
        """
        Capture interesting information about the xAPI enrollment (registration) event transmission.

        Arguments:
            xapi_transmission (XAPILearnerDataTransmissionAudit): Transmission audit object being updated
            course_grade (Numeric): Grade value for the enrollment
            course_completed: (Boolean/Numeric): Whether or not the enrollment is considered complete.
            completed_timestamp (Datetime): The point in time when completion occurred.
            status (Numeric):  The response status code
            error_message (String):  Information describing any error state provided by the caller

        Returns:
            None
        """
        xapi_transmission.course_completed = course_completed
        xapi_transmission.completed_timestamp = completed_timestamp
        xapi_transmission.grade = course_grade
        xapi_transmission.status = status
        xapi_transmission.error_message = error_message
        xapi_transmission.save()

        LOGGER.info(
            "[Integrated Channel][xAPI] Successfully updated the XAPILearnerDataTransmissionAudit object with id: {id}"
            ", user: {username} and course: {course_id}".format(
                id=xapi_transmission.id,
                username=xapi_transmission.user.username,
                course_id=xapi_transmission.course_id
            )
        )
