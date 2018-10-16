# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` api decorators module.
"""
from __future__ import absolute_import, unicode_literals

import unittest
from importlib import import_module

from faker import Factory as FakerFactory
from pytest import mark, raises
from rest_framework.exceptions import PermissionDenied
from rest_framework.reverse import reverse

from django.conf import settings
from django.test import RequestFactory

from enterprise.api.v1.decorators import enterprise_customer_required
from test_utils import mock_view_function
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


@mark.django_db
class TestEnterpriseAPIDecorators(unittest.TestCase):
    """
    Tests for enterprise API decorators.
    """
    def setUp(self):
        """
        Set up test environment.
        """
        super(TestEnterpriseAPIDecorators, self).setUp()
        faker = FakerFactory.create()
        self.provider_id = faker.slug()  # pylint: disable=no-member
        self.uuid = faker.uuid4()  # pylint: disable=no-member
        self.customer = EnterpriseCustomerFactory(uuid=self.uuid)
        self.user = UserFactory()
        self.session_engine = import_module(settings.SESSION_ENGINE)

    def _prepare_request(self, url, user):
        """
        Prepare request for test.
        """
        request = RequestFactory().get(url)
        request.user = user
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        request.session = self.session_engine.SessionStore(session_key)
        return request

    def test_enterprise_customer_required_raises_403(self):
        """
        Test that the decorator `enterprise_customer_required` raises
        PermissionDenied if the current user is not associated with
        an EnterpriseCustomer.
        """
        view_function = mock_view_function()
        url = reverse('catalogs-courses', (1, ))
        request = self._prepare_request(url, self.user)

        with raises(PermissionDenied):
            enterprise_customer_required(view_function)(request)

    def test_enterprise_customer_required_calls_view(self):
        """
        Test that the decorator `enterprise_customer_required` calls
        the decorated function if the current user is associated
        with an EnterpriseCustomer and passes the EnterpriseCustomer
        to the decorated function.
        """
        view_function = mock_view_function()
        url = reverse('catalogs-courses', (1,))
        request = self._prepare_request(url, self.user)
        EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.customer,
        )

        enterprise_customer_required(view_function)(request)

        call_args, __ = view_function.call_args  # pylint: disable=unpacking-non-sequence
        assert str(call_args[1].uuid) == str(self.customer.uuid)
