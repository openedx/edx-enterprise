"""
Admin integration for configuring Blackboard app to communicate with Blackboard systems.
"""

from six.moves.urllib.parse import urljoin

from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from enterprise.utils import get_configuration_value
from integrated_channels.blackboard.models import BlackboardEnterpriseCustomerConfiguration

LMS_OAUTH_REDIRECT_URL = urljoin(settings.LMS_ROOT_URL, '/blackboard/oauth-complete')


@admin.register(BlackboardEnterpriseCustomerConfiguration)
class BlackboardEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for BlackEnterpriseCustomerConfiguration.
    """
    list_display = (
        "enterprise_customer_name",
        "client_id",
        "client_secret",
        "blackboard_base_url",
    )

    readonly_fields = (
        "enterprise_customer_name",
        "refresh_token",
        "oauth_authorization_url",
    )

    search_fields = ("enterprise_customer_name",)

    class Meta:
        model = BlackboardEnterpriseCustomerConfiguration

    def enterprise_customer_name(self, obj):
        """
        Returns: the name for the attached EnterpriseCustomer.

        Args:
            obj: The instance of BlackboardEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        return obj.enterprise_customer.name

    def oauth_authorization_url(self, obj):
        """
        Returns: the oauth authorization url when the blackboard_base_url and client_id are available.

        Args:
            obj: The instance of BlackboardEnterpriseCustomerConfiguration
                being rendered with this admin form.
        """
        if obj.blackboard_base_url and obj.client_id:
            return format_html((f'<a href="{obj.blackboard_base_url}/learn/api/public/v1/oauth2/authorizationcode'
                                f'?redirect_uri={LMS_OAUTH_REDIRECT_URL}&'
                                f'scope=read%20write%20delete%20offline&response_type=code&'
                                f'client_id={obj.client_id}&state={obj.enterprise_customer.uuid}">Authorize Link</a>'))
        else:
            return None
