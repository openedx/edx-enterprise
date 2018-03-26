# -*- coding: utf-8 -*-
"""
Tests for Degreed Learner Data exporters.
"""

from __future__ import absolute_import, unicode_literals

import datetime
import unittest

import ddt
import mock
from freezegun import freeze_time
from pytest import mark

from django.utils import timezone

from integrated_channels.degreed.exporters.learner_data import DegreedLearnerExporter
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestDegreedLearnerExporter(unittest.TestCase):
    """
    Tests of DegreedLearnerExporter class.
    """

    NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    NOW_TIMESTAMP = 1483326245000

    def setUp(self):
        self.user = factories.UserFactory(username='C3PO', id=1, email='degreed@email.com')
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.data_sharing_consent = factories.DataSharingConsentFactory(
            username=self.user.username,
            course_id=self.course_id,
            enterprise_customer=self.enterprise_customer,
            granted=True,
        )
        self.config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            active=True,
        )
        self.idp = factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer
        )
        tpa_client_mock = mock.patch('enterprise.models.ThirdPartyAuthApiClient')
        self.tpa_client = tpa_client_mock.start()
        self.tpa_client.return_value.get_remote_id.return_value = 'fake-remote-id'
        self.addCleanup(tpa_client_mock.stop)
        super(TestDegreedLearnerExporter, self).setUp()

    @ddt.data(
        (None, False),
        (None, True),
        (NOW, False),
        (NOW, True),
    )
    @ddt.unpack
    @freeze_time(NOW)
    def test_get_learner_data_record(self, completed_date, is_passing):
        """
        The base ``get_learner_data_record`` method returns a ``LearnerDataTransmissionAudit`` with appropriate values.
        """
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        exporter = DegreedLearnerExporter('fake-user', self.config)
        learner_data_record = exporter.get_learner_data_record(
            enterprise_course_enrollment,
            completed_date=completed_date,
            is_passing=is_passing,
        )

        assert learner_data_record.enterprise_course_enrollment_id == enterprise_course_enrollment.id
        assert learner_data_record.degreed_user_email == 'degreed@email.com'
        assert learner_data_record.course_id == enterprise_course_enrollment.course_id
        assert learner_data_record.course_completed == (completed_date is not None and is_passing)
        assert learner_data_record.completed_timestamp == (
            self.NOW.strftime('%F') if completed_date is not None else None
        )

    def test_no_remote_id(self):
        """
        If the TPA API Client returns no remote user ID, nothing is returned.
        """
        self.tpa_client.return_value.get_remote_id.return_value = None
        exporter = DegreedLearnerExporter('fake-user', self.config)
        assert exporter.get_learner_data_record(factories.EnterpriseCourseEnrollmentFactory()) is None
