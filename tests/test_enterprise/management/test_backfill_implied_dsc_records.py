"""
Tests for the django management command `backfill_implied_dsc_records`.
"""

import ddt
from pytest import mark, raises
from testfixtures import LogCapture

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from consent.helpers import IMPLIED_CONSENT_CHANGE_REASON
from consent.models import DataSharingConsent
from enterprise.management.commands.backfill_implied_dsc_records import MESSAGE_FORMAT
from enterprise.models import EnterpriseCustomer
from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
)

LOGGER_NAME = 'enterprise.management.commands.backfill_implied_dsc_records'


@mark.django_db
@ddt.ddt
class BackfillImpliedDSCRecordsCommandTests(TestCase):
    """
    Test command `backfill_implied_dsc_records`.
    """
    command = 'backfill_implied_dsc_records'

    def setUp(self):
        super().setUp()
        self.course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.course_key = 'edX+DemoX'
        self.other_course_id = 'course-v1:edX+E2E-101+course'
        self.externally_managed_customer = EnterpriseCustomerFactory()
        self.other_externally_managed_customer = EnterpriseCustomerFactory()
        self.at_enrollment_customer = EnterpriseCustomerFactory()

        # Enrollments are created before the customers are switched to externally managed consent,
        # mirroring historical enrollments that never got a consent record.
        self.learner = self._create_enrollment(self.externally_managed_customer, self.course_id)
        self._create_enrollment(self.externally_managed_customer, self.other_course_id, self.learner)
        self.other_learner = self._create_enrollment(self.other_externally_managed_customer, self.course_id)
        self.at_enrollment_learner = self._create_enrollment(self.at_enrollment_customer, self.course_id)
        for enterprise_customer in [self.externally_managed_customer, self.other_externally_managed_customer]:
            enterprise_customer.enforce_data_sharing_consent = EnterpriseCustomer.EXTERNALLY_MANAGED
            enterprise_customer.save()

    def _create_enrollment(self, enterprise_customer, course_id, enterprise_customer_user=None):
        """
        Create an enterprise course enrollment and return its enterprise customer user.
        """
        enterprise_customer_user = enterprise_customer_user or EnterpriseCustomerUserFactory(
            enterprise_customer=enterprise_customer,
        )
        EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course_id,
        )
        return enterprise_customer_user

    def _consent_granted(self, enterprise_customer, enterprise_customer_user, course_id):
        """
        Return the granted value of the matching consent record, or None if there is no record.
        """
        consent_record = DataSharingConsent.objects.filter(
            enterprise_customer=enterprise_customer,
            username=enterprise_customer_user.username,
            course_id=course_id,
        ).first()
        return consent_record.granted if consent_record else None

    def test_backfill_all_externally_managed_customers(self):
        """
        Every enrollment of an externally managed customer without a consent record gets a granted record.
        """
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command)

        assert self._consent_granted(self.externally_managed_customer, self.learner, self.course_id) is True
        assert self._consent_granted(self.externally_managed_customer, self.learner, self.other_course_id) is True
        assert self._consent_granted(self.other_externally_managed_customer, self.other_learner, self.course_id) is True
        assert self._consent_granted(self.at_enrollment_customer, self.at_enrollment_learner, self.course_id) is None
        assert DataSharingConsent.objects.count() == 3
        for consent_record in DataSharingConsent.objects.all():
            assert consent_record.history.first().history_change_reason == IMPLIED_CONSENT_CHANGE_REASON
        assert "'Created Record Count': 3" in log.records[-1].message
        created_record_message = '[Implied DSC Backfill] Created ' + MESSAGE_FORMAT.format(
            self.externally_managed_customer.uuid, self.learner.username, self.course_id
        )
        assert created_record_message in [record.message for record in log.records]

    def test_backfill_single_customer(self):
        """
        Only enrollments of the given enterprise customer are backfilled.
        """
        call_command(self.command, '--enterprise-customer-uuid', str(self.externally_managed_customer.uuid))

        assert self._consent_granted(self.externally_managed_customer, self.learner, self.course_id) is True
        assert self._consent_granted(self.externally_managed_customer, self.learner, self.other_course_id) is True
        assert self._consent_granted(self.other_externally_managed_customer, self.other_learner, self.course_id) is None
        assert DataSharingConsent.objects.count() == 2

    def test_backfill_with_no_commit(self):
        """
        A dry run reports the records to be created without writing them.
        """
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command, '--no-commit')

        assert not DataSharingConsent.objects.exists()
        assert "'Created Record Count': 3" in log.records[-1].message
        to_be_created_record_message = '[Implied DSC Backfill] To be created ' + MESSAGE_FORMAT.format(
            self.externally_managed_customer.uuid, self.learner.username, self.course_id
        )
        assert to_be_created_record_message in [record.message for record in log.records]

    @ddt.data(
        # Real run, consent revoked for one of the learner's course runs.
        {'commit': True, 'revoked_at_course_level': False},
        # Real run, consent revoked for the course; a new course run record would take precedence over it.
        {'commit': True, 'revoked_at_course_level': True},
        # Dry runs must report the same counts as real runs.
        {'commit': False, 'revoked_at_course_level': False},
        {'commit': False, 'revoked_at_course_level': True},
    )
    @ddt.unpack
    def test_backfill_skips_learner_with_revoked_consent(self, commit, revoked_at_course_level):
        """
        No consent is implied for a learner who revoked consent for any course of the customer, and the revoked
        record is left unchanged.
        """
        revoked_course_id = self.course_key if revoked_at_course_level else self.course_id
        DataSharingConsentFactory(
            enterprise_customer=self.externally_managed_customer,
            username=self.learner.username,
            course_id=revoked_course_id,
            granted=False,
        )
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command, *([] if commit else ['--no-commit']))

        assert self._consent_granted(self.externally_managed_customer, self.learner, revoked_course_id) is False
        assert self._consent_granted(self.externally_managed_customer, self.learner, self.other_course_id) is None
        expected_other_learner_consent = True if commit else None
        assert self._consent_granted(
            self.other_externally_managed_customer, self.other_learner, self.course_id
        ) is expected_other_learner_consent
        assert DataSharingConsent.objects.count() == (2 if commit else 1)
        assert "'Created Record Count': 1" in log.records[-1].message
        assert "'Skipped Revoked Consent Count': 2" in log.records[-1].message

    def test_backfill_skips_existing_records(self):
        """
        Existing consent records are left unchanged and the command is safe to re-run.
        """
        DataSharingConsentFactory(
            enterprise_customer=self.externally_managed_customer,
            username=self.learner.username,
            course_id=self.course_id,
            granted=True,
        )
        call_command(self.command)
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command)

        assert self._consent_granted(self.externally_managed_customer, self.learner, self.course_id) is True
        assert self._consent_granted(self.externally_managed_customer, self.learner, self.other_course_id) is True
        assert DataSharingConsent.objects.count() == 3
        assert "'Created Record Count': 0" in log.records[-1].message
        assert "'Existing Record Count': 3" in log.records[-1].message

    def test_backfill_fetches_usernames_per_chunk(self):
        """
        Usernames are fetched with one query per chunk of enrollments rather than one query per enrollment.
        """
        user_table = get_user_model()._meta.db_table
        with CaptureQueriesContext(connection) as context:
            call_command(self.command, '--enterprise-customer-uuid', str(self.externally_managed_customer.uuid))

        user_queries = [query for query in context.captured_queries if user_table in query['sql']]
        assert len(user_queries) == 1
        assert DataSharingConsent.objects.count() == 2

    def test_backfill_skips_unlinked_learner(self):
        """
        Enrollments of unlinked learners are skipped, since learner progress reporting excludes them.
        """
        self.learner.linked = False
        self.learner.save()
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command, '--enterprise-customer-uuid', str(self.externally_managed_customer.uuid))

        assert self._consent_granted(self.externally_managed_customer, self.learner, self.course_id) is None
        assert self._consent_granted(self.externally_managed_customer, self.learner, self.other_course_id) is None
        assert not DataSharingConsent.objects.exists()
        assert "'Created Record Count': 0" in log.records[-1].message

    def test_backfill_skips_enrollment_without_user(self):
        """
        Enrollments of enterprise learners without a linked user are skipped.
        """
        enterprise_customer_user = EnterpriseCustomerUserFactory(
            enterprise_customer=self.externally_managed_customer,
            user_id=999999,
        )
        EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
            course_id=self.course_id,
        )
        with LogCapture(LOGGER_NAME) as log:
            call_command(self.command, '--enterprise-customer-uuid', str(self.externally_managed_customer.uuid))

        assert DataSharingConsent.objects.count() == 2
        assert "'Skipped No Username Count': 1" in log.records[-1].message

    def test_backfill_rejects_customer_without_externally_managed_consent(self):
        """
        The command refuses to backfill a customer that does not have externally managed consent.
        """
        with raises(CommandError):
            call_command(self.command, '--enterprise-customer-uuid', str(self.at_enrollment_customer.uuid))

        assert not DataSharingConsent.objects.exists()
