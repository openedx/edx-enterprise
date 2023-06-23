"""
Django admin integration for xAPI.
"""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django_object_actions import DjangoObjectActions

from integrated_channels.xapi.models import XAPILRSConfiguration


@admin.register(XAPILRSConfiguration)
class XAPILRSConfigurationAdmin(DjangoObjectActions, admin.ModelAdmin):
    """
    Django admin model for XAPILRSConfiguration.
    """
    fields = (
        'enterprise_customer',
        'active',
        'endpoint',
        'version',
        'key',
        'secret',
    )

    list_display = (
        'enterprise_customer_name',
        'active',
        'endpoint',
        'modified',
    )

    raw_id_fields = (
        'enterprise_customer',
    )

    ordering = ('enterprise_customer__name', )
    list_filter = ('active', )
    search_fields = ('enterprise_customer__name',)
    change_actions = ('update_modified_time',)

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

    def update_modified_time(self, request, obj):
        """
        Updates the modified time of the customer record to retransmit courses metadata
        and redirects to configuration view with success or error message.
        """
        try: 
            obj.enterprise_customer.save()
            messages.success(
                request,
                'The xapilrs enterprise customer modified time '
                '“<XAPILRSConfiguration for Enterprise {enterprise_name}>” '
                'was saved successfully.'.format(enterprise_name=obj.enterprise_customer.name))
        except:
            messages.error(
                request,
                'The xapilrs enterprise customer modified time '
                '“<XAPILRSConfiguration for Enterprise {enterprise_name}>” '
                'was not saved successfully.'.format(enterprise_name=obj.enterprise_customer.name))
        return HttpResponseRedirect('/admin/xapi/xapilrsconfiguration/')
    update_modified_time.label = 'Update Customer Modified Time'
    update_modified_time.short_description = 'Update modified time for this Enterprise Customer to retransmit courses metadata'