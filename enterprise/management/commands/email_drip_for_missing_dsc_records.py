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

    def _get_dsc_url(self, user, course_id, enterprise_customer):
        """
        Build the data sharing consent page url

        Arguments
            user (Object): The user object
            course_id (String): The course identifier
            enterprise_customer(Object): Enterprise customer object

        Returns:
            dsc_url (String): The DSC url
        """
        learner_portal_base_url = get_configuration_value(
            'ENTERPRISE_LEARNER_PORTAL_BASE_URL',
            settings.ENTERPRISE_LEARNER_PORTAL_BASE_URL
        )
        next_url = urljoin(learner_portal_base_url, str(enterprise_customer.slug))
        course_start = None
        course_details = CourseCatalogApiClient(
            user,
            enterprise_customer.site
        ).get_course_run(course_id)
        if course_details:
            try:
                course_start = parse_lms_api_datetime(course_details.get('start'))
            except (TypeError, ValueError):
                course_start = None
        else:
            LOGGER.info(
                '[Absent DSC Course Details] Could not get course details from course catalog API. '
                'User: [%s], Course: [%s], Enterprise: [%s]',
                user.username,
                course_id,
                enterprise_customer.uuid,
            )

        if course_start and course_start < datetime.datetime.now():
            lms_course_url = urljoin(settings.LMS_ROOT_URL, '/courses/{course_id}/course')
            next_url = lms_course_url.format(course_id=course_id)
        failure_url = urljoin(settings.LMS_ROOT_URL, '/dashboard')
        return '{grant_data_sharing_url}?{params}'.format(
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

    def handle(self, *args, **options):
        """
        Management command for sending an email to learners with a missing DSC. Designed to run daily.

        Example usage:
           $ ./manage.py email_drip_for_missing_dsc_records
        """
        past_date = date.today() - timedelta(days=PAST_NUM_DAYS)
        enterprise_course_enrollments = EnterpriseCourseEnrollment.objects.select_related(
            'enterprise_customer_user'
        ).filter(created__date=past_date)

        for enterprise_enrollment in enterprise_course_enrollments:
            user = enterprise_enrollment.enterprise_customer_user.user
            username = enterprise_enrollment.enterprise_customer_user.username
            user_id = enterprise_enrollment.enterprise_customer_user.user_id
            course_id = enterprise_enrollment.course_id
            enterprise_customer = enterprise_enrollment.enterprise_customer_user.enterprise_customer
            dsc_url = self._get_dsc_url(user, course_id, enterprise_customer)
            consent = DataSharingConsent.objects.proxied_get(
                username=username,
                course_id=course_id,
                enterprise_customer=enterprise_customer
            )
            # Emit the Segment event which will be used by Braze to send the email
            if isinstance(consent, ProxyDataSharingConsent):
                utils.track_event(user_id, 'edx.bi.user.consent.absent', {
                    'course': course_id,
                    'username': username,
                    'enterprise_name': enterprise_customer.name,
                    'enterprise_uuid': enterprise_customer.uuid,
                    'dsc_url': dsc_url
                })
                LOGGER.info(
                    '[Absent DSC Email] Segment event fired for missing data sharing consent. '
                    'User: [%s], Course: [%s], Enterprise: [%s], DSC URL: [%s]',
                    username,
                    course_id,
                    enterprise_customer.uuid,
                    dsc_url
                )
