"""
Quick test script to verify admin date fields are working correctly.
Run with: python manage.py test test_admin_dates --settings=test_settings
"""
from django.test import TestCase
from django.utils import timezone
from enterprise.models import EnterpriseCustomerAdmin
from test_utils import factories


class TestAdminDatesImplementation(TestCase):
    """Test that invited_date and joined_date work correctly."""

    def test_admin_dates_fields_exist(self):
        """Test that the new date fields exist on the model."""
        user = factories.UserFactory()
        enterprise_customer = factories.EnterpriseCustomerFactory()
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        
        # Create admin with explicit dates
        now = timezone.now()
        admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=enterprise_customer_user,
            invited_date=now,
            joined_date=now
        )
        
        # Verify fields are set
        self.assertIsNotNone(admin.invited_date)
        self.assertIsNotNone(admin.joined_date)
        self.assertEqual(admin.invited_date, now)
        self.assertEqual(admin.joined_date, now)
        print("Test passed: Admin date fields are working correctly!")

    def test_invited_date_required(self):
        """Test that invited_date is required."""
        user = factories.UserFactory()
        enterprise_customer = factories.EnterpriseCustomerFactory()
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        
        # Try to create admin without invited_date - should fail
        from django.db import IntegrityError
        with self.assertRaises((IntegrityError, ValueError)):
            EnterpriseCustomerAdmin.objects.create(
                enterprise_customer_user=enterprise_customer_user,
                joined_date=timezone.now()
                # invited_date is missing - should fail
            )
        print("Test passed: invited_date is required!")

    def test_joined_date_can_be_null(self):
        """Test that joined_date can be null."""
        user = factories.UserFactory()
        enterprise_customer = factories.EnterpriseCustomerFactory()
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=user.id,
            enterprise_customer=enterprise_customer
        )
        
        # Create admin with null joined_date
        admin = EnterpriseCustomerAdmin.objects.create(
            enterprise_customer_user=enterprise_customer_user,
            invited_date=timezone.now(),
            joined_date=None  # Should be allowed
        )
        
        self.assertIsNone(admin.joined_date)
        print("Test passed: joined_date can be null!")
