"""
Django admin integration for xAPI.
"""

from django_object_actions import DjangoObjectActions

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect

from integrated_channels.xapi.models import XAPILRSConfiguration


@admin.register(XAPILRSConfiguration)
class XAPILRSConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin model for XAPILRSConfiguration.
    """
    fields = (
        "enterprise_customer",
        "active",
        "endpoint",
        "version",
        "key",
        "secret",
    )

    list_display = (
        "enterprise_customer_name",
        "active",
        "endpoint",
        "modified",
    )

    raw_id_fields = ("enterprise_customer",)

    ordering = ("enterprise_customer__name",)
    list_filter = ("active",)
    search_fields = ("enterprise_customer__name",)
    change_actions = ("force_content_metadata_transmission",)

    class Meta:
        model = XAPILRSConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Arguments:
            obj: The instance of XAPILRSConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name

    def force_content_metadata_transmission(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try:
            obj.enterprise_customer.save()
            messages.success(
                request,
                f'''The xapilrs enterprise customer content metadata
                “<XAPILRSConfiguration for Enterprise {obj.enterprise_customer.name}>”
                was updated successfully.''',
            )
        except ValidationError:
            messages.error(
                request,
                f'''The xapilrs enterprise customer content metadata
                “<XAPILRSConfiguration for Enterprise {obj.enterprise_customer.name}>”
                was not updated successfully.''',
            )
        return HttpResponseRedirect("/admin/xapi/xapilrsconfiguration/")
    force_content_metadata_transmission.label = "Force content metadata transmission"
    force_content_metadata_transmission.short_description = (
        "Force content metadata transmission for this Enterprise Customer"
    )
