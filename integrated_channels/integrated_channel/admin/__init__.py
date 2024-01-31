"""
Admin site configurations for integrated channel's Content Metadata Transmission table.
"""

from django.contrib import admin

from integrated_channels.integrated_channel.models import ApiResponseRecord, ContentMetadataItemTransmission
from integrated_channels.utils import get_enterprise_customer_from_enterprise_enrollment


class BaseLearnerDataTransmissionAuditAdmin(admin.ModelAdmin):
    """
    Base admin class to hold commonly used methods across integrated channel admin views
    """
    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer or None if customer object does not exist.
        Args:
            obj: The instance of Django model being rendered with this admin form.
        """
        ent_customer = get_enterprise_customer_from_enterprise_enrollment(obj.enterprise_course_enrollment_id)
        return ent_customer.name if ent_customer else None


@admin.action(description='Clear remote_deleted_at on ContentMetadataItemTransmission item(s)')
def clear_remote_deleted_at(modeladmin, request, queryset):  # pylint: disable=unused-argument
    queryset.update(remote_deleted_at=None)


@admin.register(ContentMetadataItemTransmission)
class ContentMetadataItemTransmissionAdmin(admin.ModelAdmin):
    """
    Admin for the ContentMetadataItemTransmission audit table
    """
    list_display = (
        'enterprise_customer',
        'integrated_channel_code',
        'content_id',
        'remote_deleted_at',
        'modified'
    )

    search_fields = (
        'enterprise_customer__name',
        'enterprise_customer__uuid',
        'integrated_channel_code',
        'content_id'
    )

    raw_id_fields = (
        'enterprise_customer',
    )

    readonly_fields = [
        'api_record',
        'api_response_status_code',
        'friendly_status_message',
    ]

    actions = [
        clear_remote_deleted_at,
    ]

    list_per_page = 1000


@admin.register(ApiResponseRecord)
class ApiResponseRecordAdmin(admin.ModelAdmin):
    """
    Admin for the ApiResponseRecord table
    """
    list_display = (
        'id',
        'status_code'
    )

    search_fields = (
        'id',
        'status_code'
    )

    readonly_fields = (
        'status_code',
        'body'
    )

    list_per_page = 1000
