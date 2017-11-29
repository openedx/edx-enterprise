# -*- coding: utf-8 -*-
"""
Tests for the base course metadata exporter.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import mock
import responses
from integrated_channels.integrated_channel.exporters.course_metadata import CourseExporter
from pytest import mark

from test_utils import factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
class TestCourseExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``CourseExporter`` class.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        # Need a non-abstract config.
        self.config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
        )

        # Mocks
        self.mock_ent_courses_api_with_pagination(
            enterprise_uuid=str(self.enterprise_customer.uuid),
            course_run_ids=['course-v1:edX+DemoX+Demo_Course_1']
        )
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestCourseExporter, self).setUp()

    @responses.activate
    def test_empty_data(self):
        """
        The base course exporter should return an empty dictionary for data.
        """
        exporter = CourseExporter('fake-user', self.config)
        assert exporter.data == {}

    @responses.activate
    def test_course_exporter_export(self):
        """
        ``CourseExporter``'s ``export`` produces a JSON dump of the course data.
        """
        exporter = CourseExporter('fake-user', self.config)
        assert next(exporter.export()) == (b'[{}]', 'POST')
