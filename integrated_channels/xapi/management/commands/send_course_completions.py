# -*- coding: utf-8 -*-
"""
Send xAPI statements to the LRS configured via admin.
"""

from __future__ import absolute_import, unicode_literals

import datetime
from logging import getLogger

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from enterprise.models import EnterpriseCustomer
from enterprise.utils import NotConnectedToOpenEdX
from integrated_channels.exceptions import ClientError
from integrated_channels.xapi.models import XAPILearnerDataTransmissionAudit, XAPILRSConfiguration
from integrated_channels.xapi.utils import send_course_completion_statement

try:
    from lms.djangoapps.grades.models import PersistentCourseGrade
except ImportError:
    PersistentCourseGrade = None

try:
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
except ImportError:
    CourseOverview = None

try:
    from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory  # pylint:disable=ungrouped-imports
except ImportError:
    CourseGradeFactory = None


LOGGER = getLogger(__name__)


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
        super(Command, self).add_arguments(parser)

    @staticmethod
    def parse_arguments(*args, **options):  # pylint: disable=unused-argument
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
        if not all((PersistentCourseGrade, CourseOverview, CourseGradeFactory)):
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
        persistent_course_grades = self.get_course_completions(lrs_configuration.enterprise_customer, days)
        users = self.prefetch_users(persistent_course_grades)
        course_overviews = self.prefetch_courses(persistent_course_grades)
        LOGGER.info(
            '[Integrated Channel][xAPI] Found %s course completion for enterprise customer: [%s] during last %s days',
            len(persistent_course_grades),
            lrs_configuration.enterprise_customer,
            days,
        )

        for persistent_course_grade in persistent_course_grades:
            error_message = None
            user = users.get(persistent_course_grade.user_id)
            course_overview = course_overviews.get(persistent_course_grade.course_id)
            course_grade = CourseGradeFactory().read(user, course_key=persistent_course_grade.course_id)
            xapi_transmission_queryset = XAPILearnerDataTransmissionAudit.objects.filter(
                user=user,
                course_id=persistent_course_grade.course_id,
                course_completed=0
            )
            if not xapi_transmission_queryset.exists():
                LOGGER.warning(
                    'XAPILearnerDataTransmissionAudit object does not exist for enterprise customer: '
                    '{enterprise_customer}, user: {username}, course: {course_id}.  Skipping transmission '
                    'of course completion statement to the configured LRS endpoint.  This is likely because '
                    'a corresponding course enrollment statement has not yet been transmitted.'.format(
                        enterprise_customer=lrs_configuration.enterprise_customer.name,
                        username=user.username if user else 'User Unavailable',
                        course_id=persistent_course_grade.course_id
                    )
                )
                continue
            fields = {'status': 500, 'error_message': None}
            try:
                response = send_course_completion_statement(lrs_configuration, user, course_overview, course_grade)
            except ClientError:
                error_message = 'Client error while sending course completion to xAPI for ' \
                                'enterprise customer: {enterprise_customer}, user: {username} ' \
                                'and course: {course_id}'.format(
                                    enterprise_customer=lrs_configuration.enterprise_customer.name,
                                    username=user.username if user else 'User Unavailable',
                                    course_id=persistent_course_grade.course_id
                                )
                LOGGER.exception(error_message)
                fields.update({'error_message': error_message})
            else:
                status = response.response.status
                fields.update({'status': status})
                if response.success:
                    LOGGER.info(
                        'Successfully sent xAPI course completion for user: {username} for course: {course_id}'.format(
                            username=user.username if user else 'User Unavailable',
                            course_id=persistent_course_grade.course_id
                        )
                    )
                    fields.update({
                        'grade': course_grade.percent,
                        'course_completed': 1,
                        'completed_timestamp': persistent_course_grade.modified
                    })
                else:
                    LOGGER.warning(
                        'Unexpected xAPI response received for user: {username} for course: {course_id}.  Please '
                        'reveiew the xAPI learner data transmission audit log for details'.format(
                            username=user.username if user else 'User Unavailable',
                            course_id=persistent_course_grade.course_id
                        )
                    )
                    fields.update({'error_message': response.data})
            xapi_transmission_queryset.update(**fields)

    def get_course_completions(self, enterprise_customer, days):
        """
        Get course completions via PersistentCourseGrade for all the learners of given enterprise customer.

        Arguments:
            enterprise_customer (EnterpriseCustomer): Include Course enrollments for learners
                of this enterprise customer.
            days (int): Include course enrollment of this number of days.

        Returns:
            (list): A list of PersistentCourseGrade objects.
        """
        return PersistentCourseGrade.objects.filter(
            passed_timestamp__gt=datetime.datetime.now() - datetime.timedelta(days=days)
        ).filter(
            user_id__in=enterprise_customer.enterprise_customer_users.values_list('user_id', flat=True)
        )

    @staticmethod
    def prefetch_users(persistent_course_grades):
        """
        Prefetch Users from the list of user_ids present in the persistent_course_grades.

        Arguments:
            persistent_course_grades (list): A list of PersistentCourseGrade.

        Returns:
            (dict): A dictionary containing user_id to user mapping.
        """
        users = User.objects.filter(
            id__in=[grade.user_id for grade in persistent_course_grades]
        )
        return {
            user.id: user for user in users
        }

    @staticmethod
    def prefetch_courses(persistent_course_grades):
        """
        Prefetch courses from the list of course_ids present in the persistent_course_grades.

        Arguments:
            persistent_course_grades (list): A list of PersistentCourseGrade.

        Returns:
            (dict): A dictionary containing course_id to course_overview mapping.
        """
        return CourseOverview.get_from_ids(
            [grade.course_id for grade in persistent_course_grades]
        )
