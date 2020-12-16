# -*- coding: utf-8 -*-
"""
Tests for the `integrated_channels.cornerstone.models` models module.
"""

import unittest

import mock
from freezegun import freeze_time
from pytest import mark, raises

from django.core.exceptions import ValidationError
from django.utils import timezone

from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration
from integrated_channels.integrated_channel.tasks import transmit_single_learner_data
from test_utils.factories import (
    EnterpriseCustomerCatalogFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)

NOW = timezone.now()


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
            active=True
        )
        self.config.save()
        self.user = UserFactory()
        EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )
        self.demo_course_run_id = 'course-v1:edX+DemoX+Demo_Course_1'

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
            mock_transmitter.return_value.transmit.assert_called_once_with('mock_learner_exporter', **kwargs)

    def test_customer_catalogs_to_transmit(self):
        """
        Test the customer_catalogs_to_transmit property.
        """
        assert len(self.config.customer_catalogs_to_transmit) == 1
        assert self.config.customer_catalogs_to_transmit[0] == self.enterprise_customer_catalog

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
