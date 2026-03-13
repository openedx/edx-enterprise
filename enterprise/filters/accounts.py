"""
Pipeline step for determining read-only account settings fields.
"""
from django.conf import settings
from openedx_filters.filters import PipelineStep

from enterprise.models import EnterpriseCustomerIdentityProvider, EnterpriseCustomerUser

# social_django is only available when running inside edx-platform; edx-enterprise can be
# used without it (e.g. in standalone test environments), so guard the import defensively.
try:
    from social_django.models import UserSocialAuth
except ImportError:
    UserSocialAuth = None

try:
    from common.djangoapps import third_party_auth  # avoid circular import at module load; not available in tests
except ImportError:
    third_party_auth = None


class AccountSettingsReadOnlyFieldsStep(PipelineStep):
    """
    Adds SSO-managed fields to the read-only account settings fields set.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.account.settings.read_only_fields.requested.v1`` filter.

    When a user is linked to an enterprise customer whose SSO identity provider has
    ``sync_learner_profile_data`` enabled, the fields listed in
    ``settings.ENTERPRISE_READONLY_ACCOUNT_FIELDS`` are added to ``readonly_fields``.
    The ``"name"`` field is only added when the user has an existing ``UserSocialAuth``
    record for the enterprise IdP backend.
    """

    def run_filter(self, readonly_fields, user):  # pylint: disable=arguments-differ
        """
        Add enterprise SSO-managed fields to the read-only fields set.

        Arguments:
            readonly_fields (set): current set of read-only account field names.
            user (User): the Django User whose account settings are being updated.

        Returns:
            dict: updated pipeline data with ``readonly_fields`` key.
        """
        try:
            enterprise_customer_user = EnterpriseCustomerUser.objects.select_related(
                'enterprise_customer'
            ).get(user_id=user.id)
        except EnterpriseCustomerUser.DoesNotExist:
            return {"readonly_fields": readonly_fields}

        enterprise_customer = enterprise_customer_user.enterprise_customer

        try:
            idp_record = EnterpriseCustomerIdentityProvider.objects.get(
                enterprise_customer=enterprise_customer
            )
        except EnterpriseCustomerIdentityProvider.DoesNotExist:
            return {"readonly_fields": readonly_fields}

        try:
            if third_party_auth is None:
                return {"readonly_fields": readonly_fields}
            identity_provider = third_party_auth.provider.Registry.get(
                provider_id=idp_record.provider_id
            )
        except Exception:  # pylint: disable=broad-except
            return {"readonly_fields": readonly_fields}

        if not identity_provider or not getattr(identity_provider, 'sync_learner_profile_data', False):
            return {"readonly_fields": readonly_fields}

        enterprise_readonly = set(getattr(settings, 'ENTERPRISE_READONLY_ACCOUNT_FIELDS', []))

        if 'name' in enterprise_readonly:
            backend_name = getattr(identity_provider, 'backend_name', None)
            has_social_auth = (
                backend_name
                and UserSocialAuth is not None
                and UserSocialAuth.objects.filter(provider=backend_name, user=user).exists()
            )
            if not has_social_auth:
                enterprise_readonly = enterprise_readonly - {'name'}

        return {"readonly_fields": readonly_fields | enterprise_readonly}
