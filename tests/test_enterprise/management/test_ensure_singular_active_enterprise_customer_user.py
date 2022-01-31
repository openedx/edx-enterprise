"""
Tests for the djagno management command `ensure_singular_active_enterprise_customer_user`.
"""

import ddt
from pytest import mark

from django.core.management import call_command
from django.test import TestCase

from enterprise.models import EnterpriseCustomerUser
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerUserFactory


@mark.django_db
@ddt.ddt
class EnsureSingularActiveEnterpriseCustomerUserCommandTests(TestCase):
    """
    Test command `ensure_singular_active_enterprise_customer_user`.
    """
    command = 'ensure_singular_active_enterprise_customer_user'

    def setUp(self):
        self.lms_user_id = 1
        self.enterprise_customer_1 = EnterpriseCustomerFactory()
        self.enterprise_customer_2 = EnterpriseCustomerFactory()
        self.ecu_1 = EnterpriseCustomerUserFactory(
            user_id=self.lms_user_id,
            enterprise_customer=self.enterprise_customer_1,
            active=True,
        )
        self.ecu_2 = EnterpriseCustomerUserFactory(
            user_id=self.lms_user_id,
            enterprise_customer=self.enterprise_customer_2,
            active=True,
        )
        super().setUp()

    def test_bulk_query_update_only_changes_provided_query(self):
        """
        Test that the `ensure_singular_active_enterprise_customer_user` command will
        ensure only one ECU object is active for a given LMS user id.
        """
        # creating the initial objects will already enforce at most 1 `active=True` object, so we
        # need to bypass the inactivate_other_customers logic to get the objects in the correct
        # "bad" state.
        assert EnterpriseCustomerUser.objects.filter(user_id=self.lms_user_id, active=True).count() == 1
        inactive_ecus = EnterpriseCustomerUser.objects.filter(user_id=self.lms_user_id, active=False)
        assert inactive_ecus.count() == 1
        inactive_ecu = inactive_ecus.first()
        inactive_ecu.active = True
        # temporarily disable side effect of inactivating other customers
        inactive_ecu.should_inactivate_other_customers = False
        inactive_ecu.save()
        # assert there are now 2 ECU instances with `active=True`
        assert EnterpriseCustomerUser.objects.filter(user_id=self.lms_user_id, active=True).count() == 2
        call_command(self.command)
        assert EnterpriseCustomerUser.objects.filter(
            user_id=self.lms_user_id,
            enterprise_customer=self.enterprise_customer_1,
            active=False,
        ).count() == 1
        assert EnterpriseCustomerUser.objects.filter(
            user_id=self.lms_user_id,
            enterprise_customer=self.enterprise_customer_2,
            active=True,
        ).count() == 1
