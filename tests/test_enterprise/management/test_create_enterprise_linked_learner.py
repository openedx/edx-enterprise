"""
Tests for the management command `create_enterprise_linked_learner`.
"""

from unittest.mock import patch

import pytest

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from enterprise.devstack_api import ensure_enterprise_groups
from enterprise.models import EnterpriseCustomerUser
from test_utils.factories import EnterpriseCustomerFactory


@patch('enterprise.devstack_api.UserProfile')
@pytest.mark.django_db
class TestCreateEnterpriseLinkedLearner(TestCase):
    """Tests for the create_enterprise_linked_learner management command."""

    command = 'create_enterprise_linked_learner'

    def setUp(self):
        ensure_enterprise_groups()
        self.enterprise = EnterpriseCustomerFactory(name='Test Enterprise')
        self.other_enterprise = EnterpriseCustomerFactory(name='Other Enterprise')
        super().setUp()

    def test_links_user_to_single_enterprise(self, _MockUserProfile):
        """Creates one active EnterpriseCustomerUser link for a single ``--enterprise-name``."""
        call_command(self.command, '--username', 'linked_learner', '--enterprise-name', 'Test Enterprise')
        assert EnterpriseCustomerUser.objects.filter(
            enterprise_customer=self.enterprise,
            active=True,
        ).count() == 1

    def test_first_enterprise_is_active(self, _MockUserProfile):
        """Marks only the first ``--enterprise-name`` as the active link when multiple are passed."""
        call_command(
            self.command,
            '--username', 'dual_learner',
            '--enterprise-name', 'Test Enterprise',
            '--enterprise-name', 'Other Enterprise',
        )
        test_ecu = EnterpriseCustomerUser.objects.get(enterprise_customer=self.enterprise)
        other_ecu = EnterpriseCustomerUser.objects.get(enterprise_customer=self.other_enterprise)
        assert test_ecu.active is True
        assert other_ecu.active is False

    def test_idempotent_for_existing_user(self, _MockUserProfile):
        """Re-running the command for the same user does not create a duplicate link."""
        call_command(self.command, '--username', 'linked_learner', '--enterprise-name', 'Test Enterprise')
        call_command(self.command, '--username', 'linked_learner', '--enterprise-name', 'Test Enterprise')
        assert EnterpriseCustomerUser.objects.filter(enterprise_customer=self.enterprise).count() == 1

    def test_raises_command_error_for_missing_enterprise(self, _MockUserProfile):
        """Raises CommandError when ``--enterprise-name`` refers to an unknown customer."""
        with pytest.raises(CommandError, match="does not exist"):
            call_command(
                self.command,
                '--username', 'linked_learner',
                '--enterprise-name', 'Nonexistent Enterprise',
            )

    def test_raises_command_error_for_duplicate_enterprise(self, _MockUserProfile):
        """Raises CommandError when the same ``--enterprise-name`` is passed more than once."""
        with pytest.raises(CommandError, match="Duplicate"):
            call_command(
                self.command,
                '--username', 'linked_learner',
                '--enterprise-name', 'Test Enterprise',
                '--enterprise-name', 'Test Enterprise',
            )
