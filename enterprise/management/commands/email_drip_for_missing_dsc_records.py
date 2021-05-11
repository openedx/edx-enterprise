# -*- coding: utf-8 -*-
"""
Django management command for sending an email to learners with missing DataSharingConsent records.
"""
import datetime
import logging
from datetime import date, timedelta
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.core.management import BaseCommand
from django.urls import reverse

from consent.models import DataSharingConsent, ProxyDataSharingConsent
from enterprise import utils
from enterprise.api_client.discovery import CourseCatalogApiClient
from enterprise.api_client.lms import parse_lms_api_datetime
from enterprise.models import EnterpriseCourseEnrollment
from enterprise.utils import get_configuration_value

LOGGER = logging.getLogger(__name__)

PAST_NUM_DAYS = 1


class Command(BaseCommand):
    """
    Django management command for sending an email to learners with missing DataSharingConsent records
    """

    def _get_course_properties(self, user, course_id, enterprise_customer):
        """
        Provide the data sharing consent page url and course title

        Arguments
            user (Object): The User object
            course_id (String): The course identifier
            enterprise_customer(Object): EnterpriseCustomer object

        Returns:
            dsc_url (String): The DSC url
            course_title (String): Title of the course
        """
        learner_portal_base_url = get_configuration_value(
            'ENTERPRISE_LEARNER_PORTAL_BASE_URL',
            settings.ENTERPRISE_LEARNER_PORTAL_BASE_URL
        )
        next_url = urljoin(learner_portal_base_url, str(enterprise_customer.slug))
        course_start = None
        course_title = ''
        course_details = CourseCatalogApiClient(
            user,
            enterprise_customer.site
        ).get_course_run(course_id)
        if course_details:
            try:
                course_start = parse_lms_api_datetime(course_details.get('start'))
                course_title = course_details.get('title')
            except (TypeError, ValueError):
                pass
        else:
            LOGGER.info(
                '[Absent DSC Course Details] Could not get course details from course catalog API. '
                'User: [%s], Course: [%s], Enterprise: [%s]',
                user.username,
                course_id,
                enterprise_customer.uuid,
            )

        if course_start and course_start < datetime.datetime.now(course_start.tzinfo):
            lms_course_url = urljoin(settings.LMS_ROOT_URL, '/courses/{course_id}/course')
            next_url = lms_course_url.format(course_id=course_id)
        failure_url = urljoin(settings.LMS_ROOT_URL, '/dashboard')
        dsc_url = '{grant_data_sharing_url}?{params}'.format(
            grant_data_sharing_url=reverse('grant_data_sharing_permissions'),
            params=urlencode(
                {
                    'next': next_url,
                    'failure_url': failure_url,
                    'enterprise_customer_uuid': enterprise_customer.uuid,
                    'course_id': course_id,
                }
            )
        )
        return dsc_url, course_title

    def get_enterprise_course_enrollments(self, options):
        """
        Get EnterpriseCourseEnrollment records according to the options
        """
        enrollment_before = options['enrollment_before']
        enterprise_course_enrollments = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        )
        if enrollment_before:
            enterprise_course_enrollments = enterprise_course_enrollments.filter(created__date__lt=enrollment_before)
        else:
            past_date = date.today() - timedelta(days=PAST_NUM_DAYS)
            enterprise_course_enrollments = enterprise_course_enrollments.filter(created__date=past_date)

        return enterprise_course_enrollments

    def emit_event(self, ec_user, course_id, enterprise_customer, greeting_name):
        """
         Emit the Segment event which will be used by Braze to send the email
        """
        dsc_url, course_title = self._get_course_properties(ec_user.user, course_id, enterprise_customer)
        utils.track_event(ec_user.user_id, 'edx.bi.user.consent.absent', {
            'course': course_id,
            'username': ec_user.username,
            'enterprise_name': enterprise_customer.name,
            'enterprise_uuid': str(enterprise_customer.uuid),
            'dsc_url': dsc_url,
            'course_title': course_title,
            'user_email': ec_user.user_email,
            'greeting_name': greeting_name
        })
        LOGGER.info(
            '[Absent DSC Email] Segment event fired for missing data sharing consent. '
            'User: [%s], Course: [%s], Enterprise: [%s], DSC URL: [%s]',
            ec_user.username,
            course_id,
            str(enterprise_customer.uuid),
            dsc_url
        )

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-commit',
            action='store_true',
            dest='no_commit',
            default=False,
            help='Dry Run, print log messages without committing anything.',
        )
        parser.add_argument(
            '--enrollment-before',
            action='store',
            dest='enrollment_before',
            default=None,
            type=datetime.date.fromisoformat,
            help='Specifies the date (format YYYY-MM-DD). Enrollments created before this date will receive DSC emails.'
        )

    def handle(self, *args, **options):
        """
        Management command for sending an email to learners with a missing DSC. Designed to run daily.

        Example usage:
           $ ./manage.py email_drip_for_missing_dsc_records
           $ ./manage.py email_drip_for_missing_dsc_records  --no-commit
           $ ./manage.py email_drip_for_missing_dsc_records  --enrollment-before 2021-05-06 --no-commit
           $ ./manage.py email_drip_for_missing_dsc_records  --enrollment-before 2021-05-06
        """
        should_commit = not options['no_commit']

        email_sent_records = []

        enterprise_course_enrollments = self.get_enterprise_course_enrollments(options)
        for enterprise_enrollment in enterprise_course_enrollments:
            ec_user = enterprise_enrollment.enterprise_customer_user
            username = ec_user.username
            user_email = ec_user.user_email
            greeting_name = user_email
            if hasattr(ec_user, 'first_name') and ec_user.first_name:
                greeting_name = ec_user.first_name
            course_id = enterprise_enrollment.course_id
            enterprise_customer = ec_user.enterprise_customer
            consent = DataSharingConsent.objects.proxied_get(
                username=username,
                course_id=course_id,
                enterprise_customer=enterprise_customer
            )
            # Emit the Segment event which will be used by Braze to send the email
            if isinstance(consent, ProxyDataSharingConsent):
                if should_commit:
                    self.emit_event(ec_user, course_id, enterprise_customer, greeting_name)
                email_sent_records.append(
                    f'User: {username}, Course: {course_id}, Enterprise: {enterprise_customer.uuid}'
                )

        LOGGER.info(
            '[Absent DSC Email] Emails sent for [%s] enrollments out of [%s] enrollments. DSC records sent to: [%s]',
            len(email_sent_records),
            enterprise_course_enrollments.count(),
            email_sent_records
        )
