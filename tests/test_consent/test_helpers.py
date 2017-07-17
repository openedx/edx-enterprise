# -*- coding: utf-8 -*-
"""
Tests for helper functions in the Consent application.
"""

from __future__ import absolute_import, unicode_literals

import ddt
from consent import helpers

from django.test import testcases

from test_utils import TEST_COURSE, TEST_USER_ID, TEST_USERNAME, TEST_UUID, create_items, factories


@ddt.ddt
class ConsentHelpersTest(testcases.TestCase):
    """
    Test cases for helper functions for the Consent application.
    """

    @ddt.data(
        (factories.UserFactory, [{'id': TEST_USER_ID, 'username': TEST_USERNAME}], True),
        (None, [{}], False)
    )
    @ddt.unpack
    def test_get_user_id(self, factory, items, returns_obj):
        if factory:
            create_items(factory, items)
        user_id = helpers.get_user_id(TEST_USERNAME)
        if returns_obj:
            self.assertEqual(user_id, TEST_USER_ID)
        else:
            self.assertIsNone(user_id)

    @ddt.data(
        (factories.EnterpriseCustomerFactory, [{'uuid': TEST_UUID}], True),
        (None, [{}], False)
    )
    @ddt.unpack
    def test_get_enterprise_customer(self, factory, items, returns_obj):
        if factory:
            create_items(factory, items)
        enterprise_customer = helpers.get_enterprise_customer(TEST_UUID)
        if returns_obj:
            self.assertIsNotNone(enterprise_customer)
        else:
            self.assertIsNone(enterprise_customer)

    @ddt.data(
        (
            factories.EnterpriseCustomerUserFactory,
            [{'user_id': TEST_USER_ID, 'enterprise_customer__uuid': TEST_UUID}],
            True
        ),
        (
            None, [{}], False
        )
    )
    @ddt.unpack
    def test_get_enterprise_customer_user(self, factory, items, returns_obj):
        if factory:
            create_items(factory, items)
        enterprise_customer = helpers.get_enterprise_customer(TEST_UUID)
        enterprise_customer_user = helpers.get_enterprise_customer_user(enterprise_customer, TEST_USER_ID)
        if returns_obj:
            self.assertIsNotNone(enterprise_customer_user)
        else:
            self.assertIsNone(enterprise_customer_user)

    @ddt.data(
        (
            factories.EnterpriseCourseEnrollmentFactory,
            [{
                'course_id': TEST_COURSE,
                'enterprise_customer_user__user_id': TEST_USER_ID,
                'enterprise_customer_user__enterprise_customer__uuid': TEST_UUID,
            }],
            True
        ),
        (
            None, [{}], False
        )
    )
    @ddt.unpack
    def test_get_enterprise_course_enrollment(self, factory, items, returns_obj):
        if factory:
            create_items(factory, items)
        enterprise_customer = helpers.get_enterprise_customer(TEST_UUID)
        enterprise_course_enrollment = helpers.get_enterprise_course_enrollment(
            TEST_USER_ID,
            TEST_COURSE,
            enterprise_customer
        )
        if returns_obj:
            self.assertIsNotNone(enterprise_course_enrollment)
        else:
            self.assertIsNone(enterprise_course_enrollment)

    @ddt.data(
        (
            factories.UserDataSharingConsentAuditFactory,
            [{
                'user__user_id': TEST_USER_ID,
                'user__enterprise_customer__uuid': TEST_UUID
            }],
            True
        ),
        (
            None, [{}], False
        )
    )
    @ddt.unpack
    def test_get_user_dsc_audit(self, factory, items, returns_obj):
        if factory:
            create_items(factory, items)
        enterprise_customer = helpers.get_enterprise_customer(TEST_UUID)
        user_dsc_audit = helpers.get_user_dsc_audit(TEST_USER_ID, enterprise_customer)
        if returns_obj:
            self.assertIsNotNone(user_dsc_audit)
        else:
            self.assertIsNone(user_dsc_audit)
