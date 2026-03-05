"""
Tests for integrated_channel retirement signal handlers.
"""
import unittest

from pytest import mark

from integrated_channels.degreed.models import DegreedLearnerDataTransmissionAudit
from integrated_channels.integrated_channel.signals import (
    retire_degreed_data_transmission,
    retire_sapsf_data_transmission,
)
from integrated_channels.sap_success_factors.models import SapSuccessFactorsLearnerDataTransmissionAudit
from test_utils.factories import (
    DegreedLearnerDataTransmissionAuditFactory,
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerUserFactory,
    SapSuccessFactorsLearnerDataTransmissionAuditFactory,
    UserFactory,
)


@mark.django_db
class TestRetireSapsfDataTransmission(unittest.TestCase):
    """
    Tests for the retire_sapsf_data_transmission signal handler.
    """

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=self.user.id)
        self.enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
        )
        self.audit = SapSuccessFactorsLearnerDataTransmissionAuditFactory(
            enterprise_course_enrollment_id=self.enrollment.id,
            sapsf_user_id='sapsf-abc123',
        )

    def _send_signal(self):
        retire_sapsf_data_transmission(sender=None, user=self.user)

    def test_clears_sapsf_user_id(self):
        self._send_signal()

        self.audit.refresh_from_db()
        assert self.audit.sapsf_user_id == ''

    def test_no_audits_with_original_sapsf_user_id_remain(self):
        self._send_signal()

        assert not SapSuccessFactorsLearnerDataTransmissionAudit.objects.filter(
            enterprise_course_enrollment_id=self.enrollment.id,
            sapsf_user_id='sapsf-abc123',
        ).exists()

    def test_idempotent_when_already_retired(self):
        self._send_signal()
        self._send_signal()

        self.audit.refresh_from_db()
        assert self.audit.sapsf_user_id == ''


@mark.django_db
class TestRetireDegreedDataTransmission(unittest.TestCase):
    """
    Tests for the retire_degreed_data_transmission signal handler.
    """

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=self.user.id)
        self.enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
        )
        self.audit = DegreedLearnerDataTransmissionAuditFactory(
            enterprise_course_enrollment_id=self.enrollment.id,
            degreed_user_email='original@degreed.example.com',
        )

    def _send_signal(self):
        retire_degreed_data_transmission(sender=None, user=self.user)

    def test_clears_degreed_user_email(self):
        self._send_signal()

        self.audit.refresh_from_db()
        assert self.audit.degreed_user_email == ''

    def test_no_audits_with_original_email_remain(self):
        self._send_signal()

        assert not DegreedLearnerDataTransmissionAudit.objects.filter(
            enterprise_course_enrollment_id=self.enrollment.id,
            degreed_user_email='original@degreed.example.com',
        ).exists()

    def test_idempotent_when_already_retired(self):
        self._send_signal()
        self._send_signal()

        self.audit.refresh_from_db()
        assert self.audit.degreed_user_email == ''
