# -*- coding: utf-8 -*-
"""
Tests for the Enterprise API permissions.
"""

from __future__ import absolute_import, unicode_literals

from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate
from waffle.models import Switch

from enterprise.api.v1.permissions import HasEnterpriseDataAPIAccess, HasEnterpriseEnrollmentAPIAccess
from enterprise.constants import ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH
from test_utils.factories import GroupFactory, UserFactory


class PermissionsTestMixin(object):
    """
    Permission Test Mixin.
    """
    def get_request(self, user=None, data=None):
        """
        :return Request object
        """
        request = APIRequestFactory().post('/', data)

        if user:
            force_authenticate(request, user=user)

        return Request(request, parsers=(JSONParser(),))


class TestIsAdminUserOrInGroupPermissions(PermissionsTestMixin, APITestCase):
    """
    Tests for Enterprise API permissions.
    """

    permissions_class_map = {
        'enterprise_enrollment_api_access': HasEnterpriseEnrollmentAPIAccess(),
    }

    def setUp(self):
        """
        Setup the test cases.
        """
        super(TestIsAdminUserOrInGroupPermissions, self).setUp()
        self.user = UserFactory(email='test@example.com', password='test', is_staff=True)

    def test_is_staff_or_user_in_group_permissions(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        for group_name in self.permissions_class_map:
            group = GroupFactory(name=group_name)
            group.user_set.add(self.user)
            request = self.get_request(user=self.user)
            self.assertTrue(self.permissions_class_map[group_name].has_permission(request, None))

    def test_not_staff_and_not_in_group_permissions(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        user = UserFactory(email='test@example.com', password='test', is_staff=False)
        for group_name in self.permissions_class_map:
            request = self.get_request(user=user)
            self.assertFalse(self.permissions_class_map[group_name].has_permission(request, None))

    def test_staff_but_not_in_group_permissions(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        user = UserFactory(email='test@example.com', password='test', is_staff=True)
        for group_name in self.permissions_class_map:
            request = self.get_request(user=user)
            self.assertTrue(self.permissions_class_map[group_name].has_permission(request, None))

    def test_not_staff_but_in_group_permissions(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        user = UserFactory(email='test@example.com', password='test', is_staff=False)
        for group_name in self.permissions_class_map:
            group = GroupFactory(name=group_name)
            group.user_set.add(user)
            request = self.get_request(user=user)
            self.assertTrue(self.permissions_class_map[group_name].has_permission(request, None))

    def test_rbac_permissions_enabled(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': True})
        for group_name in self.permissions_class_map:
            request = self.get_request(user=self.user)
            self.assertTrue(self.permissions_class_map[group_name].has_permission(request, None))


class TestIsInEnterpriseGroupPermissions(PermissionsTestMixin, APITestCase):
    """
    Tests for Enterprise API permissions.
    """

    permissions_class_map = {
        'enterprise_data_api_access': HasEnterpriseDataAPIAccess(),
    }

    def setUp(self):
        """
        Setup the test cases.
        """
        super(TestIsInEnterpriseGroupPermissions, self).setUp()
        self.user = UserFactory(email='test@example.com', password='test', is_staff=True)

    def test_is_staff_and_user_in_group_permissions(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        for group_name in self.permissions_class_map:
            group = GroupFactory(name=group_name)
            group.user_set.add(self.user)
            request = self.get_request(user=self.user)
            self.assertTrue(self.permissions_class_map[group_name].has_permission(request, None))

    def test_not_staff_and_not_in_group_permissions(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        user = UserFactory(email='test@example.com', password='test', is_staff=False)
        for group_name in self.permissions_class_map:
            request = self.get_request(user=user)
            self.assertFalse(self.permissions_class_map[group_name].has_permission(request, None))

    def test_staff_but_not_in_group_permissions(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        user = UserFactory(email='test@example.com', password='test', is_staff=True)
        for group_name in self.permissions_class_map:
            request = self.get_request(user=user)
            self.assertFalse(self.permissions_class_map[group_name].has_permission(request, None))

    def test_not_staff_but_in_group_permissions(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': False})
        user = UserFactory(email='test@example.com', password='test', is_staff=False)
        for group_name in self.permissions_class_map:
            group = GroupFactory(name=group_name)
            group.user_set.add(user)
            request = self.get_request(user=user)
            self.assertTrue(self.permissions_class_map[group_name].has_permission(request, None))

    def test_rbac_permissions_enabled(self):
        Switch.objects.update_or_create(name=ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH, defaults={'active': True})
        for group_name in self.permissions_class_map:
            request = self.get_request(user=self.user)
            self.assertTrue(self.permissions_class_map[group_name].has_permission(request, None))
