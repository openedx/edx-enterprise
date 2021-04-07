# -*- coding: utf-8 -*-
"""
Django management command for sending an email to learners with missing DataSharingConsent records.
"""
import logging
from datetime import date, timedelta

from django.core.management import BaseCommand

from consent.models import DataSharingConsent, ProxyDataSharingConsent
from enterprise import utils
from enterprise.models import EnterpriseCourseEnrollment

LOGGER = logging.getLogger(__name__)

PAST_NUM_DAYS = 1


class Command(BaseCommand):
    """
    Django management command for sending an email to learners with missing DataSharingConsent records
    """

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
            username = enterprise_enrollment.enterprise_customer_user.username
            user_id = enterprise_enrollment.enterprise_customer_user.user_id
            course_id = enterprise_enrollment.course_id
            enterprise_customer = enterprise_enrollment.enterprise_customer_user.enterprise_customer
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
                    'enterprise_uuid': enterprise_customer.uuid
                })
                LOGGER.info(
                    '[Absent DSC Email] Email sent for missing data sharing consent. '
                    'User: [%s], Course: [%s], Enterprise: [%s]',
                    username,
                    course_id,
                    enterprise_customer.uuid
                )
