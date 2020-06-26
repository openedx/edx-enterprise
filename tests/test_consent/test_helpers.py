# -*- coding: utf-8 -*-
"""
Tests for helper functions in the Consent application.
"""

import ddt
from pytest import mark

from django.test import testcases

from consent import helpers
from test_utils import TEST_UUID


@mark.django_db
@ddt.ddt
class ConsentHelpersTest(testcases.TestCase):
    """
    Test cases for helper functions for the Consent application.
    """

    def test_get_data_sharing_consent_no_enterprise(self):
        """
        Test that the returned consent record is None when no EnterpriseCustomer exists.
        """
        assert helpers.get_data_sharing_consent('bob', TEST_UUID, course_id='fake-course') is None
