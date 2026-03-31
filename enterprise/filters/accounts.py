"""
Pipeline step for determining read-only account settings fields.
"""
from openedx_filters.filters import PipelineStep
from social_django.models import UserSocialAuth

from django.conf import settings

try:
    from common.djangoapps import third_party_auth
except ImportError:
    third_party_auth = None

from enterprise.models import EnterpriseCustomerIdentityProvider, EnterpriseCustomerUser


class AccountSettingsEnterpriseReadOnlyFieldsStep(PipelineStep):
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
        enterprise_customer_user = (
            EnterpriseCustomerUser.objects.filter(user_id=user.id)
            .order_by('-active', '-modified')
            .select_related('enterprise_customer')
            .first()
        )
        if not enterprise_customer_user:
            return {"readonly_fields": readonly_fields, "user": user}

        enterprise_customer = enterprise_customer_user.enterprise_customer

        idp_qs = EnterpriseCustomerIdentityProvider.objects.filter(
            enterprise_customer=enterprise_customer
        )

        # look for default provider in case of multiple, or default to first
        idp_record = idp_qs.filter(default_provider=True).first() or idp_qs.first()
        if not idp_record:
            return {"readonly_fields": readonly_fields, "user": user}

        identity_provider = third_party_auth.provider.Registry.get(
            provider_id=idp_record.provider_id
        )

        if not identity_provider or not getattr(identity_provider, 'sync_learner_profile_data', False):
            return {"readonly_fields": readonly_fields, "user": user}

        enterprise_readonly = set(getattr(settings, 'ENTERPRISE_READONLY_ACCOUNT_FIELDS', []))

        if 'name' in enterprise_readonly:
            backend_name = getattr(identity_provider, 'backend_name', None)
            has_social_auth = (
                backend_name
                and UserSocialAuth.objects.filter(provider=backend_name, user=user).exists()
            )
            if not has_social_auth:
                enterprise_readonly = enterprise_readonly - {'name'}

        return {"readonly_fields": readonly_fields | enterprise_readonly, "user": user}
