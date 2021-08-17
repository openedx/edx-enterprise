# -*- coding: utf-8 -*-
"""
Django management command for creating EnterpriseCourseEnrollment records.
"""

import logging

from django.core.management import BaseCommand
from django.db import connection

from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerUser,
    EnterpriseEnrollmentSource,
)

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Creates EnterpriseCourseEnrollment records (if they do not already exist) for CourseEnrollment records
    that are associated with an enterprise user and a course run that exists in the enterprise's catalog.
    """
    help = 'Create EnterpriseCourseEnrollment records for CourseEnrollment records associated with an enterprise.'

    def add_arguments(self, parser):
        parser.add_argument(
            '-e',
            '--enterprise_customer_uuid',
            action='store',
            dest='enterprise_customer_uuid',
            default=None,
            help='Run this command for only the given EnterpriseCustomer UUID.'
        )

    def handle(self, *args, **options):
        LOGGER.info("Command has started...")
        enterprise_customer_uuid_filter = options.get('enterprise_customer_uuid')
        records_created = 0
        records_failed = 0

        missing_enrollment_data = self._fetch_course_enrollment_data(
            enterprise_customer_uuid_filter
        )
        LOGGER.info('System has %s missing enrollments', len(missing_enrollment_data))
        for item in missing_enrollment_data:
            course_exist_in_catalog = False
            user_id = item['user_id']
            course_run_id = item['course_run_id']
            enterprise_customer_uuid = item['enterprise_customer_uuid']

            LOGGER.info(
                'Trying to create the enrollment for user [%s] in course [%s] for enterprise customer [%s]',
                user_id,
                course_run_id,
                enterprise_customer_uuid
            )

            enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)

            try:
                LOGGER.info(
                    'Checking whether course [%s] exists in enterprise customer [%s] - [%s] catalog',
                    course_run_id,
                    enterprise_customer_uuid,
                    enterprise_customer.name
                )
                course_exist_in_catalog = enterprise_customer.catalog_contains_course(course_run_id)
            except Exception as exc:    # pylint: disable=broad-except
                records_failed += 1
                LOGGER.warning(
                    'Course [%s] does not exist in EnterpriseCustomer [%s] due to this exception: [%s]',
                    course_run_id,
                    enterprise_customer.uuid,
                    str(exc)
                )

            if course_exist_in_catalog:
                enterprise_customer_user = EnterpriseCustomerUser.objects.filter(
                    enterprise_customer=enterprise_customer_uuid,
                    user_id=user_id
                )

                # This is an extra check for preventing the exception.
                # We already have implemented the solution for this (soft deletion).
                if enterprise_customer_user.exists():
                    enterprise_customer_user = enterprise_customer_user.first()
                    __, created = EnterpriseCourseEnrollment.objects.get_or_create(
                        enterprise_customer_user=enterprise_customer_user,
                        course_id=course_run_id,
                        defaults={
                            'source': EnterpriseEnrollmentSource.get_source(
                                EnterpriseEnrollmentSource.MANAGEMENT_COMMAND
                            )
                        }
                    )
                    if created:
                        # if we have enrolled the user in a course then we should
                        # active this record and inactive all the other records.
                        enterprise_customer_user.active = True
                        enterprise_customer_user.save()
                        EnterpriseCustomerUser.inactivate_other_customers(user_id, enterprise_customer)

                        records_created += 1
                        LOGGER.info(
                            'EnterpriseCourseEnrollment created: EnterpriseCustomer [%s] - User [%s] - CourseRun [%s]',
                            enterprise_customer_uuid,
                            user_id,
                            course_run_id
                        )
                    else:
                        LOGGER.warning(
                            'EnterpriseCourseEnrollment exists: EnterpriseCustomer [%s] - User [%s] - CourseRun [%s]',
                            enterprise_customer_uuid,
                            user_id,
                            course_run_id
                        )
                else:
                    LOGGER.info(
                        'User [%s] is not linked with EnterpriseCustomer - [%s]',
                        user_id,
                        enterprise_customer.uuid,
                    )

        LOGGER.info('Created %s missing EnterpriseCourseEnrollments.', records_created)
        LOGGER.info('Exception raised for %s records.', records_failed)

    def _fetch_course_enrollment_data(self, enterprise_customer_uuid):
        """
        Return enterprise customer UUID/user_id/course_run_id triples which represent CourseEnrollment records
        which do not have a matching EnterpriseCourseEnrollment record.

        The query used below looks for CourseEnrollment records that are associated with enterprise
        learners where the enrollment data is after the creation of the link between the learner
        and the enterprise. It also excludes learners with edx.org email addresses in order to
        filter out test users.
        """
        LOGGER.info("Trying to fetch the data from Database with enterprise customer [%s]", enterprise_customer_uuid)
        query = '''
            SELECT
                au.id as user_id,
                ecu.enterprise_customer_id as enterprise_customer_uuid,
                sce.course_id as course_run_id
            FROM student_courseenrollment sce
            JOIN auth_user au
                ON au.id = sce.user_id
            JOIN enterprise_enterprisecustomeruser ecu
                ON ecu.user_id = au.id
            LEFT JOIN enterprise_enterprisecourseenrollment ece
                ON ece.enterprise_customer_user_id = ecu.id
                AND ece.course_id = sce.course_id
            WHERE
                ecu.linked = true
                AND ece.id IS NULL
                AND ecu.created <= sce.created
                AND au.email NOT LIKE '%@edx.org'
                {enterprise_customer_filter}
            ORDER BY sce.created;
        '''

        with connection.cursor() as cursor:
            if enterprise_customer_uuid:
                cursor.execute(
                    query.format(enterprise_customer_filter='AND ecu.enterprise_customer_id = %s'),
                    [enterprise_customer_uuid]
                )
            else:
                cursor.execute(
                    query.format(enterprise_customer_filter='')
                )

            return self._dictfetchall(cursor)

    def _dictfetchall(self, cursor):
        """ Return all rows from a cursor as a dict. """
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]
