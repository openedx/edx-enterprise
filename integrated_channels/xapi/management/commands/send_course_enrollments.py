# -*- coding: utf-8 -*-
"""
Send xAPI statements to the LRS configured via admin.
"""

import datetime
from logging import getLogger

import six

from django.core.management.base import BaseCommand, CommandError

from enterprise.api_client.discovery import get_course_catalog_api_service_client
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer
from enterprise.utils import NotConnectedToOpenEdX
from integrated_channels.xapi.models import XAPILearnerDataTransmissionAudit, XAPILRSConfiguration
from integrated_channels.xapi.utils import is_success_response, send_course_enrollment_statement

try:
    from common.djangoapps.student.models import CourseEnrollment
except ImportError:
    CourseEnrollment = None

LOGGER = getLogger(__name__)


class Command(BaseCommand):
    """
    Send xAPI statements to all Enterprise Customers.
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
        Parse and validate arguments for send_course_enrollments command.

        Arguments:
            *args: Positional arguments passed to the command
            **options: optional arguments passed to the command

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
            except EnterpriseCustomer.DoesNotExist as no_user_error:
                raise CommandError('Enterprise customer with uuid "{enterprise_customer_uuid}" does not exist.'.format(
                    enterprise_customer_uuid=enterprise_customer_uuid
                )) from no_user_error

        return days, enterprise_customer

    def handle(self, *args, **options):
        """
        Send xAPI statements.
        """
        if not CourseEnrollment:
            raise NotConnectedToOpenEdX("This package must be installed in an OpenEdX environment.")

        days, enterprise_customer = self.parse_arguments(*args, **options)

        if enterprise_customer:
            try:
                lrs_configuration = XAPILRSConfiguration.objects.get(
                    active=True,
                    enterprise_customer=enterprise_customer
                )
            except XAPILRSConfiguration.DoesNotExist as no_config_error:
                raise CommandError('No xAPI Configuration found for "{enterprise_customer}"'.format(
                    enterprise_customer=enterprise_customer.name
                )) from no_config_error

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
            days (int): Include course enrollment of this number of days.
        """
        course_enrollments = self.get_course_enrollments(lrs_configuration.enterprise_customer, days)
        course_catalog_client = get_course_catalog_api_service_client(site=lrs_configuration.enterprise_customer.site)
        for course_enrollment in course_enrollments:

            course_overview = course_enrollment.course
            courserun_id = six.text_type(course_overview.id)
            course_run_identifiers = course_catalog_client.get_course_run_identifiers(courserun_id)
            course_overview.course_key = course_run_identifiers['course_key']
            course_overview.course_uuid = course_run_identifiers['course_uuid']

            response_fields = Command.transmit_course_enrollment_statement(
                lrs_configuration,
                course_enrollment.user,
                course_overview
            )

            if is_success_response(response_fields):
                Command.transmit_courserun_enrollment_statement(
                    lrs_configuration,
                    course_enrollment.user,
                    course_overview
                )

    @staticmethod
    def transmit_enrollment_statement(lrs_configuration, user, course_overview, object_type):
        """
        Transmits an xAPI enrollment statement for the specified object type.  If successful,
        records a transmission audit record.
        """
        response_fields = {'status': 500, 'error_message': None}
        response_fields = send_course_enrollment_statement(
            lrs_configuration,
            user,
            course_overview,
            object_type,
            response_fields
        )

        return response_fields

    @staticmethod
    def transmit_course_enrollment_statement(lrs_configuration, user, course_overview):
        """
        Transmits an xAPI enrollment statement for a course object
        """
        object_type = 'course'
        response_fields = Command.transmit_enrollment_statement(lrs_configuration, user, course_overview, object_type)

        if is_success_response(response_fields):
            courserun_id = six.text_type(course_overview.id)
            enterprise_course_enrollment_id = EnterpriseCourseEnrollment.get_enterprise_course_enrollment_id(
                user,
                courserun_id,
                lrs_configuration.enterprise_customer
            )

            Command.save_xapi_learner_data_transmission_audit(
                user,
                course_overview.course_key,
                enterprise_course_enrollment_id,
                response_fields.get('status'),
                response_fields.get('error_message')
            )
        return response_fields

    @staticmethod
    def transmit_courserun_enrollment_statement(lrs_configuration, user, course_overview):
        """
        Transmits an xAPI enrollment statement for a courserun object
        """
        object_type = 'courserun'
        response_fields = Command.transmit_enrollment_statement(lrs_configuration, user, course_overview, object_type)

        if is_success_response(response_fields):
            courserun_id = six.text_type(course_overview.id)
            enterprise_course_enrollment_id = EnterpriseCourseEnrollment.get_enterprise_course_enrollment_id(
                user,
                courserun_id,
                lrs_configuration.enterprise_customer
            )

            Command.save_xapi_learner_data_transmission_audit(
                user,
                courserun_id,
                enterprise_course_enrollment_id,
                response_fields.get('status'),
                response_fields.get('error_message')
            )
        return response_fields

    @staticmethod
    def is_already_transmitted(xapi_transmissions, user_id, course_id):
        """
        Determines if an xAPI transmission has already taken place for the specified enrollment

        Arguments:
            xapi_transmissions (QuerySet)
            user_id (Numeric)
            course_id (String)

        Returns
            Queryset
        """
        return xapi_transmissions.filter(user_id=user_id, course_id=course_id)

    @staticmethod
    def get_pertinent_course_enrollments(course_enrollments, xapi_transmissions):
        """
        Compares course enrollments to xAPI transmission records and determines which
        enrollments have not yet been transmitted

        Arguments:
            course_enrollments (QuerySet)
            xapi_transmissions (QuerySet)

        Returns
            list
        """
        pertinent_enrollments = []
        for enrollment in course_enrollments:
            if not Command.is_already_transmitted(xapi_transmissions, enrollment.user_id, enrollment.course_id):
                pertinent_enrollments.append(enrollment)
        return pertinent_enrollments

    def get_course_enrollments(self, enterprise_customer, days):
        """
        Get course enrollments for all the learners of given enterprise customer.

        Arguments:
            enterprise_customer (EnterpriseCustomer): Include Course enrollments for learners
                of this enterprise customer.
            days (int): Include course enrollment of this number of days.

        Returns:
            (list): A list of CourseEnrollment objects.
        """
        enterprise_enrollment_ids = EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user__enterprise_customer=enterprise_customer
        )
        xapi_transmissions = XAPILearnerDataTransmissionAudit.objects.filter(
            enterprise_course_enrollment_id__in=enterprise_enrollment_ids
        )

        course_enrollments = CourseEnrollment.objects.filter(
            created__gt=datetime.datetime.now() - datetime.timedelta(days=days)
        ).filter(user_id__in=enterprise_customer.enterprise_customer_users.values_list('user_id', flat=True))

        pertinent_enrollments = self.get_pertinent_course_enrollments(course_enrollments, xapi_transmissions)

        LOGGER.info(
            '[Integrated Channel][xAPI] Found %s course enrollments for enterprise customer: [%s] during last %s days',
            len(pertinent_enrollments),
            enterprise_customer,
            days,
        )

        return pertinent_enrollments

    @staticmethod
    def save_xapi_learner_data_transmission_audit(user, course_id, enterprise_course_enrollment_id,
                                                  status, error_message):

        """
        Capture interesting information about the xAPI enrollment (registration) event transmission.

        Arguments:
            user (User): User object
            course_id (String): Course or courserun key
            enterprise_course_enrollment_id (Numeric): EnterpriseCourseEnrollment identifier
            status (Numeric):  The response status code
            error_message (String):  Information describing any error state provided by the caller

        Returns:
            None
        """

        xapi_transmission, created = XAPILearnerDataTransmissionAudit.objects.get_or_create(
            user=user,
            course_id=course_id,
            defaults={
                'enterprise_course_enrollment_id': enterprise_course_enrollment_id,
                'status': status,
                'error_message': error_message
            }
        )

        if created:
            LOGGER.info(
                "[Integrated Channel][xAPI] Successfully created the XAPILearnerDataTransmissionAudit object with "
                "id: {id}, user: {username} and course: {course_id}".format(
                    id=xapi_transmission.id,
                    username=xapi_transmission.user.username,
                    course_id=xapi_transmission.course_id
                )
            )
