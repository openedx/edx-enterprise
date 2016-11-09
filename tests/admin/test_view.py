# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` admin forms module.
"""
from __future__ import absolute_import, unicode_literals

import json

import ddt
import six
from pytest import mark

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from enterprise import admin as enterprise_admin
from enterprise.admin import EnterpriseCustomerManageLearnersView
from enterprise.django_compatibility import reverse
from enterprise.models import EnterpriseCustomerUser, PendingEnterpriseCustomerUser
from test_utils.factories import (FAKER, EnterpriseCustomerFactory, EnterpriseCustomerUserFactory,
                                  PendingEnterpriseCustomerUserFactory, UserFactory)


@ddt.ddt
@mark.django_db
@override_settings(ROOT_URLCONF="test_utils.admin_urls")
# TODO: remove suppression when https://github.com/landscapeio/pylint-django/issues/78 is fixed
# pylint: disable=no-member
class TestEnterpriseCustomerManageLearnersView(TestCase):
    """
    Tests EnterpriseCustomerManageLearnersView.
    """
    def setUp(self):
        """
        Test set up - installs common dependencies.
        """
        super(TestEnterpriseCustomerManageLearnersView, self).setUp()
        self.user = UserFactory(is_staff=True, is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.default_context = {
            "has_permission": True,
            "opts": self.enterprise_customer._meta,
            "user": self.user
        }
        self.view_url = reverse(
            "admin:" + enterprise_admin.utils.UrlNames.MANAGE_LEARNERS,
            args=(self.enterprise_customer.uuid,)
        )
        self.client = Client()
        self.context_parameters = EnterpriseCustomerManageLearnersView.ContextParameters

    def _test_common_context(self, actual_context, context_overrides=None):
        """
        Test common context parts.
        """
        expected_context = {}
        expected_context.update(self.default_context)
        expected_context.update(context_overrides or {})

        for context_key, expected_value in six.iteritems(expected_context):
            assert actual_context[context_key] == expected_value

    @staticmethod
    def _assert_no_record(email):
        """
        Assert that linked user record with specified email does not exist.
        """
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 0
        try:
            user = User.objects.get(email=email)
            assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0
        except User.DoesNotExist:
            pass

    def test_get_not_logged_in(self):
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie

        response = self.client.get(self.view_url)

        assert response.status_code == 302

    def _test_get_response(self, response, linked_learners, pending_linked_learners):
        """
        Test view GET response for common parts.
        """
        assert response.status_code == 200
        self._test_common_context(response.context)
        assert list(response.context[self.context_parameters.LEARNERS]) == linked_learners
        assert list(response.context[self.context_parameters.PENDING_LEARNERS]) == pending_linked_learners
        assert response.context[self.context_parameters.ENTERPRISE_CUSTOMER] == self.enterprise_customer
        assert not response.context[self.context_parameters.MANAGE_LEARNERS_FORM].is_bound

    def test_get_empty_links(self):
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in

        response = self.client.get(self.view_url)
        self._test_get_response(response, [], [])

    def test_get_existing_links_only(self):
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in

        users = [
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
        ]

        response = self.client.get(self.view_url)
        self._test_get_response(response, users, [])

    def test_get_existing_and_pending_links(self):
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in

        linked_learners = [
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
        ]
        pending_linked_learners = [
            PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
            PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer),
        ]

        response = self.client.get(self.view_url)
        self._test_get_response(response, linked_learners, pending_linked_learners)

    def test_post_not_logged_in(self):
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie

        response = self.client.post(self.view_url, data={})

        assert response.status_code == 302

    @ddt.data(
        "test@example.com", "adam.jensen@sarif.com",
    )
    def test_post_new_user_by_email(self, email):
        # precondition checks:
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in
        self._assert_no_record(email)  # there're no record with current email

        response = self.client.post(self.view_url, data={"email": email})

        assert response.status_code == 200
        self._test_common_context(response.context)
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1
        assert list(response.context[self.context_parameters.LEARNERS]) == []
        assert len(response.context[self.context_parameters.PENDING_LEARNERS]) == 1
        assert response.context[self.context_parameters.PENDING_LEARNERS][0].user_email == email
        assert not response.context[self.context_parameters.MANAGE_LEARNERS_FORM].is_bound

    @ddt.unpack
    @ddt.data(
        ("TestGuy", "test@example.com"),
        ("AdamJensen", "adam.jensen@sarif.com"),
    )
    def test_post_new_user_by_username(self, username, email):
        # precondition checks:
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in
        self._assert_no_record(email)  # there're no record with current email

        user = UserFactory(username=username, email=email)

        response = self.client.post(self.view_url, data={"email": username})

        assert response.status_code == 200
        self._test_common_context(response.context)
        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1
        assert list(response.context[self.context_parameters.PENDING_LEARNERS]) == []
        assert len(response.context[self.context_parameters.LEARNERS]) == 1
        assert response.context[self.context_parameters.LEARNERS][0].user_id == user.id
        assert not response.context[self.context_parameters.MANAGE_LEARNERS_FORM].is_bound

    def test_post_invalid_email(self):
        # precondition checks:
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in
        assert len(EnterpriseCustomerUser.objects.all()) == 0  # there're no link records
        assert len(PendingEnterpriseCustomerUser.objects.all()) == 0  # there're no pending link records

        response = self.client.post(self.view_url, data={"email": "invalid_email"})

        assert response.status_code == 200
        self._test_common_context(response.context)
        assert len(EnterpriseCustomerUser.objects.all()) == 0
        assert response.context[self.context_parameters.MANAGE_LEARNERS_FORM].is_bound

    def _test_post_existing_record_response(self, response):
        """
        Test view POST response for common parts.
        """
        assert response.status_code == 200
        self._test_common_context(response.context)
        manage_learners_form = response.context[self.context_parameters.MANAGE_LEARNERS_FORM]
        assert manage_learners_form.is_bound
        assert "email" in manage_learners_form.errors
        assert len(manage_learners_form.errors["email"]) >= 1

    def test_post_existing_record(self):
        # precondition checks:
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in

        email = FAKER.email()

        user = UserFactory(email=email)
        EnterpriseCustomerUserFactory(user_id=user.id)
        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1
        response = self.client.post(self.view_url, data={"email": email})
        self._test_post_existing_record_response(response)
        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1

    def test_post_existing_pending_record(self):
        # precondition checks:
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in

        email = FAKER.email()

        PendingEnterpriseCustomerUserFactory(user_email=email)
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1

        response = self.client.post(self.view_url, data={"email": email})
        self._test_post_existing_record_response(response)
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1

    def test_delete_not_logged_in(self):
        assert settings.SESSION_COOKIE_NAME not in self.client.cookies  # precondition check - no session cookie

        response = self.client.delete(self.view_url, data={})

        assert response.status_code == 302

    def test_delete_not_linked(self):
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in
        email = FAKER.email()
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 404
        expected_message = "Email {email} is not linked to Enterprise Customer {ec_name}".format(
            email=email, ec_name=self.enterprise_customer.name
        )
        assert response.content.decode("utf-8") == expected_message

    def test_delete_linked(self):
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in

        email = FAKER.email()
        user = UserFactory(email=email)
        EnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_id=user.id)
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 1

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 200
        assert json.loads(response.content.decode("utf-8")) == {}
        assert len(EnterpriseCustomerUser.objects.filter(user_id=user.id)) == 0

    def test_delete_linked_pending(self):
        assert self.client.login(username=self.user.username, password="QWERTY")  # make sure we've logged in

        email = FAKER.email()
        query_string = six.moves.urllib.parse.urlencode({"unlink_email": email})

        PendingEnterpriseCustomerUserFactory(enterprise_customer=self.enterprise_customer, user_email=email)

        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 1

        response = self.client.delete(self.view_url + "?" + query_string)

        assert response.status_code == 200
        assert json.loads(response.content.decode("utf-8")) == {}
        assert len(PendingEnterpriseCustomerUser.objects.filter(user_email=email)) == 0
