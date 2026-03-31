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

        The original code migrated from openedx-platform can be distilled into 3 logical branches:

        1. If NO identify provider (IdP) has sync enabled → no readonly fields added.
        2. If one or more IdPs have sync enabled, AND user has social auth → append ALL readonly fields.
        3. If one or more IdPs have sync enabled, AND user has NO social auth → append readonly fields MINUS 'name'.

        Each return statement below is marked with the corresponding branch number.

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
            # Logical branch #1 (early exit)
            return {"readonly_fields": readonly_fields, "user": user}

        enterprise_customer = enterprise_customer_user.enterprise_customer

        idp_records = list(
            EnterpriseCustomerIdentityProvider.objects
            .filter(enterprise_customer=enterprise_customer)
        )

        # Track whether any IdP for the customer is configured to sync learner profile data. If none are, then we can
        # safely allow all fields to be editable since they won't get overwritten by the sync process
        sync_learner_profile_data = False

        # Accumulate a list of all identity providers for the customer. If the learner does NOT have any social auth
        # account configured with these backends, then we can safely allow them to edit the 'name' field (full name)
        provider_backend_names = []

        for idp in idp_records:
            identity_provider = third_party_auth.provider.Registry.get(
                provider_id=idp.provider_id
            )
            if identity_provider and getattr(identity_provider, 'sync_learner_profile_data', False):
                sync_learner_profile_data = True

            backend_name = getattr(identity_provider, 'backend_name', None)
            if backend_name:
                provider_backend_names.append(backend_name)

        # If none of the IdPs for the customer are configured to sync, allow the fields to be editable
        if not sync_learner_profile_data:
            # Logical branch #1
            return {"readonly_fields": readonly_fields, "user": user}

        # Determine if the learner has social auth configured.
        has_social_auth = False
        if provider_backend_names:
            has_social_auth = UserSocialAuth.objects.filter(
                provider__in=provider_backend_names, user=user
            ).exists()

        enterprise_readonly = set(getattr(settings, 'ENTERPRISE_READONLY_ACCOUNT_FIELDS', []))

        # If the learner does NOT have social auth configured, then at least allow them to edit their name.
        if not has_social_auth:
            enterprise_readonly = enterprise_readonly - {'name'}

        # Logical branch #2 and #3
        return {"readonly_fields": readonly_fields | enterprise_readonly, "user": user}
