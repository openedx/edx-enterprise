# -*- coding: utf-8 -*-
"""
Django management command for creating EnterpriseCourseEnrollment records.
"""
from __future__ import absolute_import, unicode_literals

import logging

from edx_rest_api_client.exceptions import HttpClientError
from requests.exceptions import RequestException
from slumber.exceptions import SlumberBaseException

from django.core.management import BaseCommand, CommandError

from enterprise.api_client.lms import CourseApiClient, EnrollmentApiClient
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Creates EnterpriseCourseEnrollment records (if they do not already exist)
    using the provided EnterpriseCustomer UUID for users enrolled in the
    provided list of courses.
    """
    help = 'Create EnterpriseCourseEnrollment records for all users enrolled in the provided list of course runs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-e',
            '--enterprise_uuid',
            action='store',
            dest='enterprise_uuid',
            default=None,
            help='EnterpriseCustomer UUID.'
        )
        parser.add_argument(
            '-c',
            '--courses',
            action='store',
            dest='courses_ids',
            default='',
            help='Comma-delimited string of course run IDs.'
        )

    def handle(self, *args, **options):
        enterprise_uuid = options.get('enterprise_uuid')
        course_ids = [course_id.strip() for course_id in options.get('courses_ids', '').split(',')]

        if not enterprise_uuid or not course_ids:
            raise CommandError('Please provide the enterprise UUID and comma-delimited list of course run IDs.')

        try:
            enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_uuid)  # pylint: disable=no-member
        except EnterpriseCustomer.DoesNotExist:
            raise CommandError('No enterprise customer found for UUID: {uuid}'.format(uuid=enterprise_uuid))

        enterprise_learners = enterprise_customer.enterprise_customer_users.all()
        for course_id in course_ids:
            if not self.get_course_details(course_id):
                LOGGER.warning('Course {course} not found, skipping.'.format(course=course_id))
                continue

            enrolled_users_count, ent_course_enrollments_count = self.create_enterprise_course_enrollments(
                course_id,
                enterprise_learners
            )

            LOGGER.info(
                'Created {created} missing EnterpriseCourseEnrollments '
                'for {enrolled} enterprise learners enrolled in {course}.'.format(
                    created=ent_course_enrollments_count,
                    enrolled=enrolled_users_count,
                    course=course_id
                )
            )

    def get_course_details(self, course_id):
        """
        Returns course details for the given course or None if the course details
        could not be retrieved from the LMS courses API.

        Arguments:
            course_id (string): The course ID.

        Returns:
            dict: The course details or None if the course could not be retrieved.
        """
        try:
            return CourseApiClient().get_course_details(course_id)
        except (RequestException, SlumberBaseException, HttpClientError):
            LOGGER.error('Failed to retrieve course details from LMS API for {course}'.format(course=course_id))

        return None

    def create_enterprise_course_enrollments(self, course_id, enterprise_learners):
        """
        Create EnterpriseCourseEnrollments (if they do not exist) for each provided enterprise
        learner in the provided course if the user is already enrolled in the given course.

        Arguments:
            course_id (string): The course ID.
            enterprise_learners (list): List of EnterpriseCustomerUsers.

        Returns:
            tuple: Number of enrolled users in the course, Number of EnterpriseCourseEnrollments created.
        """
        enrolled_users_count = 0
        ent_course_enrollments_count = 0
        for enterprise_learner in enterprise_learners:
            course_enrollment = EnrollmentApiClient().get_course_enrollment(enterprise_learner.user.username, course_id)

            # If user is enrolled in the course, create EnterpriseCourseEnrollment.
            if course_enrollment:
                enrolled_users_count += 1
                __, created = EnterpriseCourseEnrollment.objects.get_or_create(
                    enterprise_customer_user=enterprise_learner,
                    course_id=course_id,
                )

                if created:
                    ent_course_enrollments_count += 1

        return enrolled_users_count, ent_course_enrollments_count
