"""
Tests for custom enterprise_support Serializers.
"""
from uuid import uuid4

from django.test import TestCase

from enterprise.models import LicensedEnterpriseCourseEnrollment
from enterprise.platform_support.serializers import EnterpriseCourseEnrollmentSerializer
from test_utils.factories import EnterpriseCourseEnrollmentFactory, EnterpriseCustomerUserFactory


class EnterpriseCourseEnrollmentSerializerTests(TestCase):
    """
    Tests for EnterpriseCourseEnrollmentSerializer.
    """

    @classmethod
    def setUpTestData(cls):
        enterprise_customer_user = EnterpriseCustomerUserFactory()
        enterprise_course_enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user
        )
        cls.enterprise_customer_user = enterprise_customer_user
        cls.enterprise_course_enrollment = enterprise_course_enrollment

    def test_data_with_license(self):
        """ Verify the correct fields are serialized when the enrollment is licensed. """

        license_uuid = uuid4()
        licensed_ece = LicensedEnterpriseCourseEnrollment(
            license_uuid=license_uuid,
            enterprise_course_enrollment=self.enterprise_course_enrollment
        )
        licensed_ece.save()

        serializer = EnterpriseCourseEnrollmentSerializer(self.enterprise_course_enrollment)

        expected = {
            'enterprise_customer_name': self.enterprise_customer_user.enterprise_customer.name,
            'enterprise_customer_user_id': self.enterprise_customer_user.id,
            'course_id': self.enterprise_course_enrollment.course_id,
            'saved_for_later': self.enterprise_course_enrollment.saved_for_later,
            'license': {
                'uuid': str(license_uuid),
                'is_revoked': licensed_ece.is_revoked,
            }
        }
        assert serializer.data == expected

    def test_data_without_license(self):
        """ Verify the correct fields are serialized when the enrollment is not licensed. """

        serializer = EnterpriseCourseEnrollmentSerializer(self.enterprise_course_enrollment)

        expected = {
            'enterprise_customer_name': self.enterprise_customer_user.enterprise_customer.name,
            'enterprise_customer_user_id': self.enterprise_customer_user.id,
            'course_id': self.enterprise_course_enrollment.course_id,
            'saved_for_later': self.enterprise_course_enrollment.saved_for_later,
            'license': None
        }
        assert serializer.data == expected
