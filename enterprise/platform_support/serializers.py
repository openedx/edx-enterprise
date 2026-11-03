"""
Defines serializers for platform_support.
"""


from rest_framework import serializers

from enterprise.api.v1.serializers import (
    EnterpriseCourseEnrollmentReadOnlySerializer as BaseEnterpriseCourseEnrollmentSerializer,
)
from enterprise.models import EnterpriseCourseEnrollment


class EnterpriseCourseEnrollmentSerializer(BaseEnterpriseCourseEnrollmentSerializer):
    """
    Serializer for EnterpriseCourseEnrollment model.
    """

    enterprise_customer_name = serializers.SerializerMethodField()
    license = serializers.SerializerMethodField()

    class Meta:
        model = EnterpriseCourseEnrollment
        fields = (
            'course_id',
            'enterprise_customer_name',
            'enterprise_customer_user_id',
            'license',
            'saved_for_later'
        )

    def get_enterprise_customer_name(self, obj):
        """Return the name of the customer this enrollment belongs to."""
        return obj.enterprise_customer_user.enterprise_customer.name

    def get_license(self, obj):
        """Return the subscription license backing this enrollment, if any."""
        licensed_ece = obj.license

        if licensed_ece:
            return {
                'uuid': str(licensed_ece.license_uuid),
                'is_revoked': licensed_ece.is_revoked
            }
        return None
