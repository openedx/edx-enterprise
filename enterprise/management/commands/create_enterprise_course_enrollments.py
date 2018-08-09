# -*- coding: utf-8 -*-
"""
Django management command for creating EnterpriseCourseEnrollment records.
"""
from __future__ import absolute_import, unicode_literals

import logging

from django.core.management import BaseCommand
from django.db import connection

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer, EnterpriseCustomerUser

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
        enterprise_customer_uuid_filter = options.get('enterprise_customer_uuid')
        records_created = 0

        missing_enrollment_data = self._fetch_course_enrollment_data(
            enterprise_customer_uuid_filter
        )
        for item in missing_enrollment_data:
            enterprise_customer_uuid = item['enterprise_customer_uuid']
            user_id = item['user_id']
            course_run_id = item['course_run_id']

            # pylint: disable=no-member
            enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_customer_uuid)
            if enterprise_customer.catalog_contains_course(course_run_id):
                enterprise_customer_user = EnterpriseCustomerUser.objects.get(
                    enterprise_customer=enterprise_customer_uuid,
                    user_id=user_id
                )

                # pylint: disable=no-member
                __, created = EnterpriseCourseEnrollment.objects.get_or_create(
                    enterprise_customer_user=enterprise_customer_user,
                    course_id=course_run_id
                )
                if created:
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

        LOGGER.info('Created %s missing EnterpriseCourseEnrollments.', records_created)

    def _fetch_course_enrollment_data(self, enterprise_customer_uuid):
        """
        Return enterprise customer UUID/user_id/course_run_id triples which represent CourseEnrollment records
        which do not have a matching EnterpriseCourseEnrollment record.

        The query used below looks for CourseEnrollment records that are associated with enterprise
        learners where the enrollment data is after the creation of the link between the learner
        and the enterprise. It also excludes learners with edx.org email addresses in order to
        filter out test users.
        """
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
                ece.id IS NULL
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
