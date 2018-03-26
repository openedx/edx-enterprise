# -*- coding: utf-8 -*-
"""
Tests for the base course metadata transmitter.
"""

from __future__ import absolute_import, unicode_literals

import unittest

import ddt
import mock
from pytest import mark

from integrated_channels.integrated_channel.transmitters.course_metadata import CourseTransmitter
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestCourseTransmitter(unittest.TestCase):
    """
    Tests for the class ``CourseTransmitter``.
    """

    def setUp(self):
        super(TestCourseTransmitter, self).setUp()
        enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')
        # We need some non-abstract configuration for these things to work,
        # so it's okay for it to be any arbitrary channel. We randomly choose SAPSF.
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer,
            key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            secret="client_secret",
        )
        self.global_config = factories.SAPSuccessFactorsGlobalConfigurationFactory()

        # Mocks
        create_course_content_mock = mock.patch(
            'integrated_channels.integrated_channel.client.IntegratedChannelApiClient.create_course_content'
        )
        self.create_course_content_mock = create_course_content_mock.start()
        self.create_course_content_mock.return_value = 200, '{}'
        self.addCleanup(create_course_content_mock.stop)
        delete_course_content_mock = mock.patch(
            'integrated_channels.integrated_channel.client.IntegratedChannelApiClient.delete_course_content'
        )
        self.delete_course_content_mock = delete_course_content_mock.start()
        self.delete_course_content_mock.return_value = 200, '{}'
        self.addCleanup(delete_course_content_mock.stop)

    @ddt.data(
        ('create_course_content_mock', 'POST'),
        ('delete_course_content_mock', 'DELETE'),
    )
    @ddt.unpack
    def test_transmit_block_post(self, mocked_method, http_method):
        """
        Passing in a HTTP method to ``transmit_block`` should correspond to calling the appropriate client method.
        """
        transmitter = CourseTransmitter(self.enterprise_config)
        transmitter.transmit_block('fake-course-block', method=http_method)
        getattr(self, mocked_method).assert_called_once_with('fake-course-block')

    def test_transmit_block_unrecognized_method(self):
        """
        Passing in an unrecognized method to ``transmit_block`` throws a ``ValueError``.
        """
        transmitter = CourseTransmitter(self.enterprise_config)
        with self.assertRaises(ValueError):
            transmitter.transmit_block('fake-course-block', method='UNRECOGNIZED-METHOD')
