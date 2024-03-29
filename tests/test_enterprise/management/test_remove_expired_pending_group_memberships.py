"""
Tests for the django management command `remove_expired_pending_group_memberships`.
"""
from datetime import timedelta

from pytest import mark

from django.core.management import call_command
from django.test import TestCase

from enterprise import models
from enterprise.utils import localized_utcnow
from test_utils import factories


@mark.django_db
class RemoveExpiredPendingGroupMembershipsCommandTests(TestCase):
    """
    Test command `remove_expired_pending_group_memberships`.
    """
    command = 'remove_expired_pending_group_memberships'

    def test_specifying_a_customer_limits_command_scope(self):
        """
        Test that if the command is passed an optional ``--enterprise_customer`` arg, it will limit the scope of
        queryable objects to just that customer's memberships
        """
        # Target membership that should be removed because it has a pending user and is over 90 days old
        group_to_remove_from = factories.EnterpriseGroupFactory()
        membership_to_remove = factories.EnterpriseGroupMembershipFactory(
            group=group_to_remove_from,
            enterprise_customer_user=None,
        )
        membership_to_remove.created = localized_utcnow() - timedelta(days=91)
        membership_to_remove.save()

        # A membership that is older than 90 days but connected to a different customer
        membership_to_keep = factories.EnterpriseGroupMembershipFactory(
            enterprise_customer_user=None,
        )
        membership_to_keep.created = localized_utcnow() - timedelta(days=91)
        membership_to_keep.save()

        call_command(self.command, enterprise_customer=str(group_to_remove_from.enterprise_customer.uuid))

        assert not models.EnterpriseGroupMembership.all_objects.filter(pk=membership_to_remove.pk)
        assert not models.PendingEnterpriseCustomerUser.objects.filter(
            pk=membership_to_remove.pending_enterprise_customer_user.pk
        )

        assert models.EnterpriseGroupMembership.all_objects.filter(pk=membership_to_keep.pk)
        assert models.PendingEnterpriseCustomerUser.objects.filter(
            pk=membership_to_keep.pending_enterprise_customer_user.pk
        )

        # Sanity check
        call_command(self.command)
        assert not models.EnterpriseGroupMembership.all_objects.filter(pk=membership_to_keep.pk)
        assert not models.PendingEnterpriseCustomerUser.objects.filter(
            pk=membership_to_keep.pending_enterprise_customer_user.pk
        )

    def test_removing_old_records(self):
        """
        Test that the command properly hard deletes membership records and pending enterprise customer user records
        """
        # Target membership that should be removed because it has a pending user and is over 90 days old
        membership_to_remove = factories.EnterpriseGroupMembershipFactory(
            enterprise_customer_user=None,
        )
        membership_to_remove.created = localized_utcnow() - timedelta(days=91)
        membership_to_remove.save()

        # A membership that is older than 90 days but has a realized enterprise customer user
        old_membership_to_keep = factories.EnterpriseGroupMembershipFactory(
            pending_enterprise_customer_user=None,
        )
        old_membership_to_keep.created = localized_utcnow() - timedelta(days=91)
        old_membership_to_keep.save()

        # A membership that has a pending user but has not reached the 90 days cutoff
        new_pending_membership = factories.EnterpriseGroupMembershipFactory(
            enterprise_customer_user=None,
        )
        new_pending_membership.created = localized_utcnow()

        # Sanity check, a membership that is younger than 90 days and has a realized enterprise customer user
        membership = factories.EnterpriseGroupMembershipFactory(
            pending_enterprise_customer_user=None,
        )
        membership.created = localized_utcnow()
        membership.save()

        call_command(self.command)

        # Assert that memberships and pending customers are removed
        assert not models.EnterpriseGroupMembership.all_objects.filter(pk=membership_to_remove.pk)
        assert not models.PendingEnterpriseCustomerUser.objects.filter(
            pk=membership_to_remove.pending_enterprise_customer_user.pk
        )

        # Assert that expected memberships and users are kept
        assert models.EnterpriseGroupMembership.all_objects.filter(pk=old_membership_to_keep.pk)
        assert models.EnterpriseCustomerUser.objects.filter(pk=old_membership_to_keep.enterprise_customer_user.pk)

        assert models.EnterpriseGroupMembership.all_objects.filter(pk=new_pending_membership.pk)
        assert models.PendingEnterpriseCustomerUser.objects.filter(
            pk=new_pending_membership.pending_enterprise_customer_user.pk
        )

        assert models.EnterpriseGroupMembership.all_objects.filter(pk=membership.pk)
        assert models.EnterpriseCustomerUser.objects.filter(pk=membership.enterprise_customer_user.pk)
