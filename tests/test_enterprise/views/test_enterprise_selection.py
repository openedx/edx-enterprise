"""
Tests for the ``EnterpriseSelectionView`` view of the Enterprise app.
"""

from unittest import mock

import ddt
from pytest import mark

from django.test import Client
from django.urls import reverse

from enterprise.forms import ENTERPRISE_SELECT_SUBTITLE
from enterprise.models import EnterpriseCustomerUser
from test_utils import EnterpriseFormViewTestCase
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory, UserFactory


@mark.django_db
@ddt.ddt
class TestEnterpriseSelectionView(EnterpriseFormViewTestCase):
    """
    Test EnterpriseSelectionView.
    """
    url = reverse('enterprise_select_active')
    template_path = 'enterprise.views.EnterpriseSelectionView.template_name'

    def setUp(self):
        self.user = UserFactory.create(is_active=True)
        self.user.set_password("QWERTY")
        self.user.save()
        self.client = Client()
        super().setUp()

        self.success_url = '/enterprise/grant_data_sharing_permissions'
        enterprises = ['Gryffindor', 'Hufflepuff', 'Ravenclaw', 'Slytherin']
        for enterprise in enterprises:
            enterprise_customer = EnterpriseCustomerFactory(name=enterprise)
            EnterpriseCustomerUserFactory(
                user_id=self.user.id,
                enterprise_customer=enterprise_customer
            )

        enterprises = EnterpriseCustomerUser.objects.filter(
            user_id=self.user.id
        ).values_list(
            'enterprise_customer__uuid', 'enterprise_customer__name'
        )
        self.enterprise_choices = [(str(uuid), name) for uuid, name in enterprises]

    def _login(self):
        """
        Log user in.
        """
        assert self.client.login(username=self.user.username, password="QWERTY")

    def test_view_unauthenticated_user(self):
        """
        Test that view will be available to logged in user only.
        """
        response = self.client.get(self.url)
        assert response.status_code == 302
        assert response.url == '/accounts/login/?next=/enterprise/select/active'

    def test_view_get(self):
        """
        Test that view HTTP GET works as expected.
        """
        self._login()
        response = self.client.get(self.url + '?success_url={}'.format(self.success_url))
        assert response.status_code == 200

        assert response.context['select_enterprise_message_title'] == 'Select an organization'
        assert response.context['select_enterprise_message_subtitle'] == ENTERPRISE_SELECT_SUBTITLE

        assert sorted(response.context['form'].fields.keys()) == sorted(['enterprise', 'success_url'])
        assert response.context['form'].fields['enterprise'].choices == self.enterprise_choices
        assert response.context['form'].fields['success_url'].initial == self.success_url

    def test_view_post(self):
        """
        Test that view HTTP POST works as expected.
        """
        self._login()
        user_id = self.user.pk

        # before selection, only 1 EnterpriseCustomerUser is active
        assert EnterpriseCustomerUser.objects.filter(user_id=user_id, active=True).count() == 1

        new_enterprise = self.enterprise_choices[2][0]
        post_data = {
            'enterprise': new_enterprise,
        }

        with mock.patch('enterprise.views.LOGGER.info') as mock_logger:
            response = self.client.post(self.url, post_data)
            assert mock_logger.called
            assert mock_logger.call_args.args == (
                '[Enterprise Selection Page] Learner activated an enterprise. User: %s, EnterpriseCustomer: %s',
                self.user.username,
                new_enterprise,
            )

        assert response.status_code == 200

        # after selection only the selected enterprise should be active for learner
        assert EnterpriseCustomerUser.objects.get(user_id=user_id, enterprise_customer=new_enterprise).active
        # selected enterprise is set correctly in the session
        self.assertEqual(self.client.session['enterprise_customer']['uuid'], new_enterprise)
        # all other enterprises for learner should be non-active
        active_ecu_count = EnterpriseCustomerUser.objects.filter(
            user_id=user_id, active=True,
        ).exclude(
            enterprise_customer=new_enterprise,
        ).count()
        assert active_ecu_count == 0

    def test_post_errors(self):
        """
        Test errors are raised if incorrect data is POSTed.
        """
        incorrect_enterprise = '111'
        errors = [
            'Enterprise not found',
            'Select a valid choice. 111 is not one of the available choices.'
        ]

        self._login()
        post_data = {
            'enterprise': incorrect_enterprise,
        }
        response = self.client.post(self.url, post_data)
        assert response.status_code == 400
        assert sorted(response.json().get('errors')) == sorted(errors)
