# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` filters module.
"""

import ddt
from pytest import mark
from rest_framework import status
from rest_framework.reverse import reverse

from django.conf import settings

from test_utils import FAKE_UUIDS, TEST_EMAIL, TEST_USERNAME, APITest, factories

ENTERPRISE_CUSTOMER_LIST_ENDPOINT = reverse('enterprise-customer-list')


@ddt.ddt
@mark.django_db
class TestUserFilterBackend(APITest):
    """
    Test suite for the ``UserFilterBackend`` filter.
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
            user_id=self.user.id,
        )

    @ddt.data(
        (False, 1),
        (True, 2),
    )
    @ddt.unpack
    def test_filter_for_list(self, is_staff, expected_data_length):
        """
        Filter objects based off of user ID -- show all for staff, but only the authenticated user himself otherwise.

        Note that the choice of endpoint below is arbitrary.
        This test could use any endpoint that makes use of the ``UserFilterBackend`` filter.
        """
        self.user.is_staff = is_staff
        self.user.save()
        factories.EnterpriseCustomerFactory()
        response = self.client.get(settings.TEST_SERVER + reverse('enterprise-customer-list'))
        assert response.status_code == status.HTTP_200_OK
        data = self.load_json(response.content)
        assert len(data['results']) == expected_data_length

    @ddt.data(
        (False, False, {'detail': 'Not found.'}),
        (False, True, {'uuid': FAKE_UUIDS[0], 'active': True}),
        (True, False, {'uuid': FAKE_UUIDS[0], 'active': True}),
        (True, True, {'uuid': FAKE_UUIDS[0], 'active': True}),
    )
    @ddt.unpack
    def test_filter_for_detail(self, is_staff, is_linked, expected_content_in_response):
        """
        Filter the specific object based off of user ID.

        Show the object for staff, and for the authenticated user if there's an association with the object
        and the user through the view's `USER_ID_FILTER`.

        Note that the choice of endpoint below is arbitrary.
        This test could use any endpoint that makes use of the ``UserFilterBackend`` filter.
        """
        self.user.is_staff = is_staff
        self.user.save()
        if not is_linked:
            self.enterprise_customer_user.user_id = self.user.id + 1
            self.enterprise_customer_user.save()
        response = self.client.get(settings.TEST_SERVER + reverse('enterprise-customer-detail', (FAKE_UUIDS[0],)))
        data = self.load_json(response.content)
        for key, value in expected_content_in_response.items():
            assert data[key] == value


@ddt.ddt
@mark.django_db
class TestEnterpriseCustomerUserFilterBackend(APITest):
    """
    Test suite for the ``EnterpriseCustomerUserFilterBackend`` filter.
    """

    def setUp(self):
        super().setUp()
        enterprise_customer = factories.EnterpriseCustomerFactory(uuid=FAKE_UUIDS[0])
        factories.EnterpriseCustomerUserFactory(enterprise_customer=enterprise_customer, user_id=self.user.id)
        self.url = settings.TEST_SERVER + reverse('enterprise-learner-list')

    @ddt.data(
        # Staff user
        (TEST_USERNAME, TEST_EMAIL, True, 1),
        (TEST_USERNAME, '', True, 1),
        ('', TEST_EMAIL, True, 1),
        ('', '', True, 1),
        ('dummy', 'dummy@example.com', True, 0),
        ('dummy', '', True, 0),
        ('', 'dummy@example.com', True, 0),
        # Non-staff user
        (TEST_USERNAME, TEST_EMAIL, False, 1),
        (TEST_USERNAME, '', False, 1),
        ('', TEST_EMAIL, False, 1),
        ('', '', False, 1),
        ('dummy', 'dummy@example.com', False, 1),
        ('dummy', '', False, 1),
        ('', 'dummy@example.com', False, 1),
    )
    @ddt.unpack
    def test_filter_by_user_attributes(self, username, email, is_staff, expected_data_length):
        """
        Filter users through email/username if requesting user is staff, otherwise based off of request user ID.
        """
        self.user.is_staff = is_staff
        self.user.save()
        response = self.client.get(self.url + "?email=" + email + "&username=" + username)
        assert response.status_code == status.HTTP_200_OK
        data = self.load_json(response.content)
        assert len(data['results']) == expected_data_length

    @ddt.data(
        ('', '', 1),
        (FAKE_UUIDS[0], '', 1),
        (FAKE_UUIDS[1], '', 0),
        ('', 'enterprise_admin', 0),
        ('', 'enterprise_learner', 0),
        (FAKE_UUIDS[0], 'enterprise_learner', 1),
        (FAKE_UUIDS[1], 'enterprise_learner', 0),
        (FAKE_UUIDS[0], 'enterprise_admin', 0),
    )
    @ddt.unpack
    @ddt.unpack
    def test_filter_by_enterprise_attributes(self, enterprise_customer_uuid, role, expected_data_length):
        """
        Filter users through enterprise_customer_uuid/role if requesting user is staff.
        """
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(self.url + "?enterprise_customer_uuid=" + enterprise_customer_uuid + "&role=" + role)

        if role and not enterprise_customer_uuid:
            assert response.status_code == status.HTTP_400_BAD_REQUEST
        else:
            assert response.status_code == status.HTTP_200_OK
            data = self.load_json(response.content)
            assert len(data['results']) == expected_data_length


@ddt.ddt
@mark.django_db
class TestEnterpriseLinkedUserFilterBackend(APITest):
    """
    Test suite for the ``EnterpriseLinkedUserFilterBackend`` filter.
    """

    def setUp(self):
        super().setUp()
        self.url = settings.TEST_SERVER + ENTERPRISE_CUSTOMER_LIST_ENDPOINT
        self.enterprise_customer_data = {
            'active': True,
            'slug': 'test-enterprise1',
            'uuid': FAKE_UUIDS[0],
            'name': 'Test Enterprise Customer',
            'enable_data_sharing_consent': True,
        }
        self.enterprise_customer = factories.EnterpriseCustomerFactory(**self.enterprise_customer_data)

    @ddt.data(
        # API should return enterprise customer details
        {'is_staff': False, 'is_linked_to_enterprise': True, 'has_access': True},
        # API should not return enterprise customer details
        {'is_staff': False, 'is_linked_to_enterprise': False, 'has_access': False},
        # for staff, API should return enterprise customer details irrespective of linked status
        {'is_staff': True, 'is_linked_to_enterprise': True, 'has_access': True},
        # for staff, API should return enterprise customer details irrespective of linked status
        {'is_staff': True, 'is_linked_to_enterprise': False, 'has_access': True},
    )
    @ddt.unpack
    def test_filter(self, is_staff, is_linked_to_enterprise, has_access):
        self.user.is_staff = is_staff
        self.user.save()

        if is_linked_to_enterprise:
            factories.EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=self.enterprise_customer,
            )

        response = self.client.get(self.url)
        response = self.load_json(response.content)

        if has_access:
            enterprise_customer_response = response['results'][0]
            for key, value in self.enterprise_customer_data.items():
                assert enterprise_customer_response[key] == value
        else:
            assert response == {'count': 0, 'next': None, 'previous': None, 'results': []}
