# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` serializer module.
"""

from __future__ import absolute_import, unicode_literals

import ddt
import mock
import six
from faker import Factory as FakerFactory
from pytest import mark, raises
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory

from django.test import override_settings

from enterprise.api.v1.serializers import EnterpriseCatalogCoursesReadOnlySerializer, ImmutableStateSerializer
from test_utils import APITest, factories


@mark.django_db
class TestImmutableStateSerializer(APITest):
    """
    Tests for enterprise API serializers which are immutable.
    """

    def setUp(self):
        """
        Perform operations common for all tests.

        Populate data base for api testing.
        """
        super(TestImmutableStateSerializer, self).setUp()
        self.instance = None
        self.data = {"data": "data"}
        self.validated_data = self.data
        self.serializer = ImmutableStateSerializer(self.data)

    def test_update(self):
        """
        Test ``update`` method of ImmutableStateSerializer.

        Verify that ``update`` for ImmutableStateSerializer returns
        successfully without making any changes.
        """
        with self.assertNumQueries(0):
            self.serializer.update(self.instance, self.validated_data)

    def test_create(self):
        """
        Test ``create`` method of ImmutableStateSerializer.

        Verify that ``create`` for ImmutableStateSerializer returns
        successfully without making any changes.
        """
        with self.assertNumQueries(0):
            self.serializer.create(self.validated_data)


@ddt.ddt
@mark.django_db
class TestEnterpriseCatalogCoursesSerializer(TestImmutableStateSerializer):
    """
    Tests for enterprise API serializers.
    """

    def setUp(self):
        """
        Perform operations common for all tests.

        Populate data base for api testing.
        """
        super(TestEnterpriseCatalogCoursesSerializer, self).setUp()
        faker = FakerFactory.create()

        self.provider_id = faker.slug()  # pylint: disable=no-member

        self.user = factories.UserFactory()
        self.ecu = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
        )
        factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.ecu.enterprise_customer,
            provider_id=self.provider_id,
        )

        # Create and authenticate a request
        self.request = APIRequestFactory().get(reverse('catalogs-list'))
        self.request.user = self.user

        # instance is none as models for this serializer do not exist in enterprise.
        self.instance = None
        self.data = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [
                {
                    'owners': [
                        {
                            'description': None,
                            'tags': [],
                            'name': '',
                            'homepage_url': None,
                            'key': 'edX',
                            'certificate_logo_image_url': None,
                            'marketing_url': None,
                            'logo_image_url': None,
                            'uuid': 'aa4aaad0-2ff0-44ce-95e5-1121d02f3b27'
                        }
                    ],
                    'uuid': 'd2fb4cb0-b538-4934-ba60-684d48ff5865',
                    'title': 'edX Demonstration Course',
                    'prerequisites': [],
                    'image': None,
                    'expected_learning_items': [],
                    'sponsors': [],
                    'modified': '2017-03-03T07:34:19.322916Z',
                    'full_description': None,
                    'subjects': [],
                    'video': None,
                    'key': 'edX+DemoX',
                    'short_description': None,
                    'marketing_url': 'http://testserver/course/course-v1:edX+DemoX+1T2017/',
                    'level_type': None,
                    'course_runs': [
                        {
                            'key': 'course-v1:edX+DemoX+1T2017',
                            'uuid': '57432370-0a6e-4d95-90fe-77b4fe64de2b',
                            'title': 'edX Demonstration Course',
                            'image': {
                                'width': None,
                                'src': 'http://testserver/image/promoted/screen_shot_2016-12-27_at_9.30.00_am.png',
                                'description': None,
                                'height': None
                            },
                            'short_description': 'edX Demonstration Course',
                            'marketing_url': 'http://testserver/course/course-edx-d103?utm_medium=affiliate_partner',
                            'start': '2016-12-28T05:00:00Z',
                            'end': '2018-12-28T00:00:00Z',
                            'enrollment_start': None,
                            'enrollment_end': None,
                            'pacing_type': 'instructor_paced',
                            'type': 'audit',
                            'course': 'edx+D103',
                            'full_description': 'edx demo course',
                            'announcement': None,
                            'video': None,
                            'seats': [
                                {
                                    'type': 'audit',
                                    'price': '0.00',
                                    'currency': 'USD',
                                    'upgrade_deadline': None,
                                    'credit_provider': None,
                                    'credit_hours': None,
                                    'sku': '2ADB190'
                                }
                            ],
                            'content_language': 'en-us',
                            'transcript_languages': [],
                            'instructors': [],
                            'staff': [],
                            'min_effort': None,
                            'max_effort': None,
                            'modified': '2017-03-08T05:46:52.682549Z',
                            'level_type': 'Introductory',
                            'availability': 'Current',
                            'mobile_available': False,
                            'hidden': False,
                            'reporting_type': 'mooc'
                        }
                    ]
                }
            ]
        }

        self.validated_data = self.data
        self.serializer = EnterpriseCatalogCoursesReadOnlySerializer(
            self.data
        )

    @ddt.data(
        (
            {
                'key': 'course-v1:edx+D103+1T2017',
                'uuid': '57432370-0a6e-4d95-90fe-77b4fe64de2b',
                'title': 'A self-paced audit course',
                'marketing_url': 'http://testserver/course/course-v1:edX+DemoX+1T2017/?'
                                 'utm_source=test_user&utm_medium=affiliate_partner'

            },
            1,
            'test-shib',
            '47130371-0b6d-43f5-01de-71942664de2b',
            {
                'key': 'course-v1:edx+D103+1T2017',
                'uuid': '57432370-0a6e-4d95-90fe-77b4fe64de2b',
                'title': 'A self-paced audit course',
            },
            {
                'marketing_url': 'http://testserver/course/course-v1:edX+DemoX+1T2017/?'
                                 'utm_source=test_user&utm_medium=affiliate_partner&'
                                 'tpa_hint=test-shib&enterprise_id=47130371-0b6d-43f5-01de-71942664de2b&catalog_id=1',
                'track_selection_url': 'http://testserver/course_modes/choose/course-v1:edX+DemoX+1T2017/?'
                                       'tpa_hint=test-shib&enterprise_id=47130371-0b6d-43f5-01de-71942664de2b&'
                                       'catalog_id=1',
            },
        ),
        (
            {
                'key': 'course-v1:edx+D103+1T2017',
                'uuid': '57432370-0a6e-4d95-90fe-77b4fe64de2b',
                'title': 'A self-paced audit course',
                'marketing_url': None,
            },
            1,
            'test-shib',
            '47130371-0b6d-43f5-01de-71942664de2b',
            {
                'key': 'course-v1:edx+D103+1T2017',
                'uuid': '57432370-0a6e-4d95-90fe-77b4fe64de2b',
                'title': 'A self-paced audit course',
                'marketing_url': None,
            },
            {
                'track_selection_url': 'http://testserver/course_modes/choose/course-v1:edX+DemoX+1T2017/?'
                                       'tpa_hint=test-shib&enterprise_id=47130371-0b6d-43f5-01de-71942664de2b&'
                                       'catalog_id=1',
            },
        ),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.configuration_helpers')
    @override_settings(LMS_ROOT_URL='http://testserver/')
    def test_update_course_runs(
            self,
            course_run,
            catalog_id,
            provider_id,
            enterprise_customer_uuid,
            expected_fields,
            expected_urls,
            mock_config_helpers,
    ):
        """
        Test update_course_runs method of EnterpriseCatalogCoursesReadOnlySerializer.

        Verify that update_course for EnterpriseCatalogCoursesReadOnlySerializer returns
        successfully without errors.
        """
        # Populate database.
        mock_config_helpers.get_value.return_value = 'http://testserver/'
        ec_identity_provider = factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer__uuid=enterprise_customer_uuid,
            provider_id=provider_id,
        )
        course_run_url = 'course_modes/choose/course-v1:edX+DemoX+1T2017/'
        enterprise_context = {
            'tpa_hint': provider_id,
            'enterprise_id': enterprise_customer_uuid,
            'catalog_id': catalog_id
        }

        with mock.patch('enterprise.utils.reverse', return_value=course_run_url):
            updated_course_runs = self.serializer.update_course_runs(
                course_runs=[course_run],
                enterprise_customer=ec_identity_provider.enterprise_customer,
                enterprise_context=enterprise_context,
            )

            assert len(updated_course_runs) == 1
            updated_course_run = updated_course_runs[0]

            # Make sure all of the expected fields are present in data returned.
            # This statement will also assert that all of the expected fields have same value.
            for key, value in six.iteritems(expected_fields):
                assert key in updated_course_run
                assert value == updated_course_run[key]

            # Make sure all expected urls are present in data returned.
            for key, value in six.iteritems(expected_urls):
                assert key in updated_course_run
                self.assert_url(value, updated_course_run[key])

    @mock.patch('enterprise.utils.reverse', return_value='')
    @mock.patch('enterprise.models.configuration_helpers')
    def test_update_course(self, mock_config_helpers, _):
        """
        Test update_course method of EnterpriseCatalogCoursesReadOnlySerializer.

        Verify that update_course for EnterpriseCatalogCoursesReadOnlySerializer returns
        successfully without errors.
        """
        mock_config_helpers.get_value.return_value = ''
        global_context = {
            'tpa_hint': self.provider_id,
            'catalog_id': 1,
        }
        course = self.data['results'][0]
        updated_course = self.serializer.update_course(course, self.ecu.enterprise_customer, global_context)

        # Make sure global context passed in to update_course is added to the course.
        assert 'tpa_hint' in updated_course
        assert updated_course['tpa_hint'] == self.provider_id

        for course_run in updated_course['course_runs']:
            assert 'track_selection_url' in course_run
            assert 'tpa_hint={}'.format(self.provider_id) in course_run['track_selection_url']

        # Make sure missing `key` in course run raises an exception
        course['course_runs'] = [{}]
        with raises(KeyError):
            self.serializer.update_course(course, self.ecu.enterprise_customer, global_context)

    @ddt.data(
        (
            {
                'key': 'edx+DemoX',
                'uuid': 'd2fb4cb0-b538-4934-ba60-684d48ff5865',
                'title': 'edX Demonstration Course',
                'course_runs': [],
            },
            'test-shib',
            {},
            {
                'key': 'edx+DemoX',
                'uuid': 'd2fb4cb0-b538-4934-ba60-684d48ff5865',
                'title': 'edX Demonstration Course',
                'course_runs': [],
            },
        ),
        (
            {
                'key': 'edx+DemoX',
                'uuid': 'd2fb4cb0-b538-4934-ba60-684d48ff5865',
                'title': 'edX Demonstration Course',
                'course_runs': [],
            },
            'test-shib',
            {
                'tpa_hint': 'test-shib',
            },
            {
                'key': 'edx+DemoX',
                'uuid': 'd2fb4cb0-b538-4934-ba60-684d48ff5865',
                'title': 'edX Demonstration Course',
                'course_runs': [],
                'tpa_hint': 'test-shib',
            },
        ),
    )
    @ddt.unpack
    @override_settings(LMS_ROOT_URL='http://testserver/')
    def test_update_course_ddt(self, course, provider_id, global_context, expected_course):
        """
        Test update_course method of EnterpriseCatalogCoursesReadOnlySerializer.

        Verify that update_course for EnterpriseCatalogCoursesReadOnlySerializer returns
        successfully without errors.
        """
        enterprise_customer_id = 'd2fb4cb0-b538-4934-1926-684d48ff5865'
        ecu = factories.EnterpriseCustomerUserFactory(
            enterprise_customer__uuid=enterprise_customer_id,
            user_id=self.user.id,
        )
        factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=ecu.enterprise_customer,
            provider_id=provider_id,
        )

        with mock.patch('enterprise.utils.reverse', return_value='course_modes/choose/'):
            updated_course = self.serializer.update_course(course, ecu.enterprise_customer, global_context)

            # Make sure global context passed in to update_course is added to the course.
            for key, value in six.iteritems(global_context):
                assert key in updated_course
                assert updated_course[key] == value

            assert expected_course == updated_course

    @mock.patch('enterprise.utils.reverse', return_value='/course_modes/choose/')
    @mock.patch('enterprise.models.configuration_helpers')
    def test_update_enterprise_courses(self, mock_config_helpers, _):
        """
        Test update_enterprise_courses method of EnterpriseCatalogCoursesReadOnlySerializer.

        Verify that update_enterprise_courses for EnterpriseCatalogCoursesReadOnlySerializer updates
        serializer data successfully without errors.
        """
        mock_config_helpers.get_value.return_value = ''
        self.serializer.update_enterprise_courses(self.ecu.enterprise_customer, catalog_id=1)

        # Make sure global context passed in to update_course is added to the course.
        assert all('tpa_hint' in course for course in self.serializer.data['results'])
        assert all(course['tpa_hint'] == self.provider_id for course in self.serializer.data['results'])
