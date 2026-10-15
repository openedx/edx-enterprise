"""
Django admin integration for configuring moodle app to communicate with Moodle systems.
"""

from django_object_actions import DjangoObjectActions

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

from integrated_channels.integrated_channel.admin import BaseLearnerDataTransmissionAuditAdmin
from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration, MoodleLearnerDataTransmissionAudit


class MoodleEnterpriseCustomerConfigurationForm(forms.ModelForm):
    """
    Django admin form for MoodleEnterpriseCustomerConfiguration.
    """
    class Meta:
        model = MoodleEnterpriseCustomerConfiguration
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        cleaned_username = cleaned_data.get('decrypted_username')
        cleaned_password = cleaned_data.get('decrypted_password')
        cleaned_token = cleaned_data.get('decrypted_token')
        if cleaned_token and (cleaned_username or cleaned_password):
            raise ValidationError(_('Cannot set both a Username/Password and Token'))
        if (cleaned_username and not cleaned_password) or (cleaned_password and not cleaned_username):
            raise ValidationError(_('Must set both a Username and Password, not just one'))


@admin.register(MoodleEnterpriseCustomerConfiguration)
class MoodleEnterpriseCustomerConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin model for MoodleEnterpriseCustomerConfiguration.
    """

    raw_id_fields = (
        'enterprise_customer',
    )

    form = MoodleEnterpriseCustomerConfigurationForm
    change_actions = ('force_content_metadata_transmission',)

    @admin.action(
        description="Force content metadata transmission for this Enterprise Customer"
    )
    def force_content_metadata_transmission(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try:
            obj.enterprise_customer.save()
            messages.success(
                request,
                f'''The moodle enterprise customer content metadata
                “<MoodleEnterpriseCustomerConfiguration for Enterprise
                {obj.enterprise_customer.name}>” was updated successfully.''',
            )
        except ValidationError:
            messages.error(
                request,
                f'''The moodle enterprise customer content metadata
                “<MoodleEnterpriseCustomerConfiguration for Enterprise
                {obj.enterprise_customer.name}>” was not updated successfully.''',
            )
        return HttpResponseRedirect(
            "/admin/moodle/moodleenterprisecustomerconfiguration"
        )
    force_content_metadata_transmission.label = "Force content metadata transmission"


@admin.register(MoodleLearnerDataTransmissionAudit)
class MoodleLearnerDataTransmissionAuditAdmin(BaseLearnerDataTransmissionAuditAdmin):
    """
    Django admin model for MoodleLearnerDataTransmissionAudit.
    """
    list_display = (
        "enterprise_course_enrollment_id",
        "course_id",
        "status",
        "modified",
    )

    readonly_fields = (
        "moodle_user_email",
        "progress_status",
        "content_title",
        "enterprise_customer_name",
        "friendly_status_message",
        "api_record",
    )

    search_fields = (
        "moodle_user_email",
        "enterprise_course_enrollment_id",
        "course_id",
        "content_title",
        "friendly_status_message"
    )

    list_per_page = 1000

    class Meta:
        model = MoodleLearnerDataTransmissionAudit
