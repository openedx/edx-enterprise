# -*- coding: utf-8 -*-
"""
Send xAPI statements to the LRS configured via admin.
"""

from __future__ import absolute_import, unicode_literals

import datetime
from logging import getLogger

import six

from django.core.management.base import BaseCommand, CommandError

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer
from enterprise.utils import NotConnectedToOpenEdX
from integrated_channels.exceptions import ClientError
from integrated_channels.xapi.models import XAPILearnerDataTransmissionAudit, XAPILRSConfiguration
from integrated_channels.xapi.utils import send_course_enrollment_statement

try:
    from student.models import CourseEnrollment
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
        super(Command, self).add_arguments(parser)

    @staticmethod
    def parse_arguments(*args, **options):  # pylint: disable=unused-argument
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
                # pylint: disable=no-member
                enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)
            except EnterpriseCustomer.DoesNotExist:
                raise CommandError('Enterprise customer with uuid "{enterprise_customer_uuid}" does not exist.'.format(
                    enterprise_customer_uuid=enterprise_customer_uuid
                ))

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
            except XAPILRSConfiguration.DoesNotExist:
                raise CommandError('No xAPI Configuration found for "{enterprise_customer}"'.format(
                    enterprise_customer=enterprise_customer.name
                ))

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
        LOGGER.info(
            '[Integrated Channel][xAPI] Found %s course enrollments for enterprise customer: [%s] during last %s days',
            len(course_enrollments),
            lrs_configuration.enterprise_customer,
            days,
        )

        for course_enrollment in course_enrollments:
            error_message = None
            course_id = six.text_type(course_enrollment.course.id)
            try:
                send_course_enrollment_statement(lrs_configuration, course_enrollment)
            except ClientError:
                error_message = 'Client error while sending course enrollment to xAPI for ' \
                                'enterprise customer: {enterprise_customer}, user: {username} ' \
                                'and course: {course_id}'.format(
                                    enterprise_customer=lrs_configuration.enterprise_customer.name,
                                    username=course_enrollment.user.username,
                                    course_id=course_id
                                )
                LOGGER.exception(error_message)
                status = 500
            else:
                LOGGER.info(
                    'Successfully send the course enrollment to xAPI for user: {username} for course: '
                    "{course_id}".format(
                        username=course_enrollment.user.username,
                        course_id=course_id
                    )
                )
                status = 200
            xapi_transmission, created = XAPILearnerDataTransmissionAudit.objects.get_or_create(
                user=course_enrollment.user,
                course_id=course_id,
                defaults={
                    'enterprise_course_enrollment_id': EnterpriseCourseEnrollment.get_enterprise_course_enrollment_id(
                        course_enrollment.user,
                        course_id,
                        lrs_configuration.enterprise_customer
                    ),
                    'status': status,
                    'error_message': error_message
                }
            )
            if created:
                LOGGER.info(
                    "Successfully created the XAPILearnerDataTransmissionAudit object with id: {id}, user: {username}"
                    " and course: {course_id}".format(
                        id=xapi_transmission.id,
                        username=xapi_transmission.user.username,
                        course_id=xapi_transmission.course_id
                    )
                )

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
        return CourseEnrollment.objects.filter(
            created__gt=datetime.datetime.now() - datetime.timedelta(days=days)
        ).filter(
            user_id__in=enterprise_customer.enterprise_customer_users.values_list('user_id', flat=True)
        )
