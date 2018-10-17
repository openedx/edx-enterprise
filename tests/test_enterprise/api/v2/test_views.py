# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api module.
"""
from __future__ import absolute_import, unicode_literals

import json
from operator import itemgetter

import mock
from pytest import mark
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from six.moves.urllib.parse import (  # pylint: disable=import-error,ungrouped-imports
    parse_qs,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import override_settings
from django.utils import timezone

from enterprise.api.v2.views import EnterpriseCustomerViewSetV2
from enterprise.models import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomer,
    EnterpriseCustomerIdentityProvider,
    EnterpriseCustomerUser,
    PendingEnrollment,
    PendingEnterpriseCustomerUser,
)
from test_utils import (
    FAKE_UUIDS,
    TEST_COURSE,
    TEST_COURSE_KEY,
    TEST_PASSWORD,
    TEST_SLUG,
    TEST_USERNAME,
    APITest,
    factories,
    fake_catalog_api,
    fake_enterprise_api,
    update_course_run_with_enterprise_context,
    update_course_with_enterprise_context,
    update_program_with_enterprise_context,
)

CATALOGS_LIST_ENDPOINT = reverse('catalogs-list')
CATALOGS_DETAIL_ENDPOINT = reverse('catalogs-detail', (1, ))
CATALOGS_COURSES_ENDPOINT = reverse('catalogs-courses', (1, ))
ENTERPRISE_CATALOGS_LIST_ENDPOINT = reverse('enterprise-catalogs-list')
ENTERPRISE_CATALOGS_DETAIL_ENDPOINT = reverse(
    'enterprise-catalogs-detail',
    kwargs={'pk': FAKE_UUIDS[1]}
)
ENTERPRISE_CATALOGS_CONTAINS_CONTENT_ENDPOINT = reverse(
    'enterprise-catalogs-contains-content-items',
    kwargs={'pk': FAKE_UUIDS[1]}
)
ENTERPRISE_CATALOGS_COURSE_ENDPOINT = reverse(
    # pylint: disable=anomalous-backslash-in-string
    r'enterprise-catalogs-courses/(?P<course-key>[^/+]+(/|\+)[^/+]+)',
    kwargs={'pk': FAKE_UUIDS[1], 'course_key': TEST_COURSE_KEY}
)
ENTERPRISE_CATALOGS_COURSE_RUN_ENDPOINT = reverse(
    # pylint: disable=anomalous-backslash-in-string
    r'enterprise-catalogs-course-runs/(?P<course-id>[^/+]+(/|\+)[^/+]+(/|\+)[^/?]+)',
    kwargs={'pk': FAKE_UUIDS[1], 'course_id': TEST_COURSE}
)
ENTERPRISE_CATALOGS_PROGRAM_ENDPOINT = reverse(
    r'enterprise-catalogs-programs/(?P<program-uuid>[^/]+)',
    kwargs={'pk': FAKE_UUIDS[1], 'program_uuid': FAKE_UUIDS[3]}
)
ENTERPRISE_COURSE_ENROLLMENT_LIST_ENDPOINT = reverse('enterprise-course-enrollment-list')
ENTERPRISE_CUSTOMER_COURSES_ENDPOINT = reverse('enterprise-customer-courses', (FAKE_UUIDS[0],))
ENTERPRISE_CUSTOMER_ENTITLEMENT_LIST_ENDPOINT = reverse('enterprise-customer-entitlement-list')
ENTERPRISE_CUSTOMER_BRANDING_LIST_ENDPOINT = reverse('enterprise-customer-branding-list')
ENTERPRISE_CUSTOMER_BRANDING_DETAIL_ENDPOINT = reverse('enterprise-customer-branding-detail', (TEST_SLUG,))
ENTERPRISE_CUSTOMER_LIST_ENDPOINT = reverse('enterprise-customer-list')
ENTERPRISE_CUSTOMER_CONTAINS_CONTENT_ENDPOINT = reverse(
    'enterprise-customer-contains-content-items',
    kwargs={'pk': FAKE_UUIDS[0]}
)
ENTERPRISE_CUSTOMER_COURSE_ENROLLMENTS_ENDPOINT = reverse('enterprise-customer-course-enrollments', (FAKE_UUIDS[0],))
ENTERPRISE_CUSTOMER_REPORTING_ENDPOINT = reverse('enterprise-customer-reporting-list')
ENTERPRISE_LEARNER_ENTITLEMENTS_ENDPOINT = reverse('enterprise-learner-entitlements', (1,))
ENTERPRISE_LEARNER_LIST_ENDPOINT = reverse('enterprise-learner-list')
ENTERPRISE_CUSTOMER_WITH_ACCESS_TO_ENDPOINT = reverse('enterprise-customer-with-access-to')


@mark.django_db
class TestEnterpriseAPIViews(APITest):
    """
    Tests for enterprise api views.
    """

    def test_enterprisecustomer_courses_v2_detail_route(self):
        """
        enterprisecustomer v2 detail route should take a enterprisecustomer id
        and then return all courses within all enterprise catalogs linked to the
        enterprise
        """
        # Create your enterprise customer
        # Create a few different catalogs associated with the enterprise customer
        # Do that enterprisecustomeruser link thing other tests did
        # Hit the new end point and assert that the correct data is being returned
        pass
