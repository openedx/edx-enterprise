# -*- coding: utf-8 -*-
"""
Tests for helper functions in the Consent application.
"""

from __future__ import absolute_import, unicode_literals

import ddt
from consent import helpers

from django.test import testcases

from test_utils import TEST_USER_ID, TEST_USERNAME, create_items, factories


@ddt.ddt
class ConsentHelpersTest(testcases.TestCase):
    """
    Test cases for helper functions for the Consent application.
    """

    @ddt.data(
        True, False
    )
    def test_consent_exists_proxy_enrollment(self, user_exists):
        """
        If we did proxy enrollment, we return ``True`` for the consent existence question.
        """
        if user_exists:
            factories.UserFactory(id=1)
        ece = factories.EnterpriseCourseEnrollmentFactory(enterprise_customer_user__user_id=1)
        consent_exists = helpers.consent_exists(
            ece.enterprise_customer_user.username,
            ece.course_id,
            ece.enterprise_customer_user.enterprise_customer.uuid,
        )
        if user_exists:
            assert consent_exists
        else:
            assert not consent_exists

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
