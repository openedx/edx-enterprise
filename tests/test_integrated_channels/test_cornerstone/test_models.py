"""
Tests for the `integrated_channels.cornerstone.models` models module.
"""

import unittest
from datetime import datetime, timezone
from unittest import mock

from freezegun import freeze_time
from pytest import mark, raises

from django.core.exceptions import ValidationError

from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration
from integrated_channels.integrated_channel.tasks import transmit_single_learner_data
from test_utils.factories import (
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerCatalogFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)

NOW = datetime.now(timezone.utc)


@mark.django_db
class TestCornerstoneEnterpriseCustomerConfiguration(unittest.TestCase):
    """
    Tests of the ``CornerstoneEnterpriseCustomerConfiguration`` model.
    """

    def setUp(self):
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_customer_catalog = EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer
        )
        self.config = CornerstoneEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer,
            catalogs_to_transmit=str(self.enterprise_customer_catalog.uuid),
            active=True,
            cornerstone_base_url='https://edx-one.csod.com'
        )
        self.config.save()
        self.config2 = CornerstoneEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer,
            catalogs_to_transmit=str(self.enterprise_customer_catalog.uuid),
            active=True,
            cornerstone_base_url='https://edx-two.csod.com'
        )
        self.config2.save()
        self.user = UserFactory()
        ecu = EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )

        ece1 = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=ecu
        )
        # Demo course must be a course user is enrolled in through
        # an enterprise customer for enterprise signal to be transmitted.
        self.demo_course_run_id = ece1.course_id

        super().setUp()

    @freeze_time(NOW)
    @mock.patch(
        'integrated_channels.cornerstone.models.CornerstoneEnterpriseCustomerConfiguration.get_learner_data_exporter'
    )
    def test_transmit_single_learner_data(self, mock_learner_exporter):
        """
        The transmit_single_learner_data is called and passes kwargs to underlying transmitter.
        """
        kwargs = {
            'learner_to_transmit': self.user,
            'course_run_id': self.demo_course_run_id,
            'completed_date': NOW,
            'grade': 'Pass',
            'is_passing': True,
        }
        mock_learner_exporter.return_value = 'mock_learner_exporter'
        with mock.patch(
                'integrated_channels.cornerstone.models.CornerstoneEnterpriseCustomerConfiguration'
                '.get_learner_data_transmitter'
        ) as mock_transmitter:
            transmit_single_learner_data(self.user.username, self.demo_course_run_id)
            mock_transmitter.return_value.transmit.assert_called_with('mock_learner_exporter', **kwargs)
            assert mock_transmitter.return_value.transmit.call_count == 2

    def test_customer_catalogs_to_transmit(self):
        """
        Test the customer_catalogs_to_transmit property.
        """
        assert len(self.config.customer_catalogs_to_transmit) == 1
        assert self.config.customer_catalogs_to_transmit[0] == self.enterprise_customer_catalog

    def test_get_by_subdomain(self):
        """
        Test the model's method for looking up a specific config by subdomain
        """
        found1 = CornerstoneEnterpriseCustomerConfiguration.get_by_customer_and_subdomain(
            self.enterprise_customer,
            'edx-one'
        )
        assert found1 == self.config
        found2 = CornerstoneEnterpriseCustomerConfiguration.get_by_customer_and_subdomain(
            self.enterprise_customer,
            'edx-two'
        )
        assert found2 == self.config2

    def test_clean(self):
        """
        Test the custom clean method of model.
        """
        # with valid catalog uuids in 'catalogs_to_transmit', clean will not raise any exception.
        self.config.clean()

        # with invalid catalog uuids in 'catalogs_to_transmit', clean will raise 'ValidationError'.
        self.config.catalogs_to_transmit = "fake-uuid,"
        self.config.save()
        with raises(ValidationError):
            self.config.clean()

        self.config.catalogs_to_transmit = str(EnterpriseCustomerCatalogFactory().uuid)
        self.config.save()
        with raises(ValidationError):
            self.config.clean()
