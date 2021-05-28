"""
Admin site configurations for integrated channel's Content Metadata Transmission table.
"""

from django.contrib import admin

from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission


@admin.register(ContentMetadataItemTransmission)
class ContentMetadataItemTransmissionAdmin(admin.ModelAdmin):
    """
    Admin for the ContentMetadataItemTransmission audit table
    """
    list_display = ('enterprise_customer', 'integrated_channel_code', 'content_id', 'channel_metadata')
    search_fields = ('enterprise_customer', 'integrated_channel_code', 'content_id')
