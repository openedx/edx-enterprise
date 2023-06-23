"""
Django admin integration for configuring moodle app to communicate with Moodle systems.
"""

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django_object_actions import DjangoObjectActions
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
        cleaned_username = cleaned_data.get('username')
        cleaned_password = cleaned_data.get('password')
        cleaned_token = cleaned_data.get('token')
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
    change_actions = ('update_modified_time',)

    def update_modified_time(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try:
            obj.enterprise_customer.save()
            messages.success(
                request,
                "The moodle enterprise customer modified time "
                "“<MoodleEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” "
                "was saved successfully.".format(
                    enterprise_name=obj.enterprise_customer.name
                ),
            )
        except ValidationError:
            messages.error(
                request,
                "The moodle enterprise customer modified time "
                "“<MoodleEnterpriseCustomerConfiguration for Enterprise {enterprise_name}>” "
                "was not saved successfully.".format(
                    enterprise_name=obj.enterprise_customer.name
                ),
            )
        return HttpResponseRedirect(
            "/admin/moodle/moodleenterprisecustomerconfiguration"
        )
    update_modified_time.label = "Update Customer Modified Time"
    update_modified_time.short_description = (
        "Update modified time for this Enterprise Customer "
    )
    "to retransmit courses metadata"


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
    )

    list_per_page = 1000

    class Meta:
        model = MoodleLearnerDataTransmissionAudit
