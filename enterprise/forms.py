# -*- coding: utf-8 -*-
"""
User-facing forms for the Enterprise app.
"""

import logging

from django import forms
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser

LOGGER = logging.getLogger(__name__)

ENTERPRISE_SELECT_SUBTITLE = _(
    u'You have access to multiple organizations. Select the organization that you will use '
    'to sign up for courses. If you want to change organizations, sign out and sign back in.'
)
ENTERPRISE_LOGIN_TITLE = _(u'Enter the organization name')
ENTERPRISE_LOGIN_SUBTITLE = _(
    u'Have an account through your company, school, or organization? Enter your organization’s name below to sign in.'
)
ERROR_MESSAGE_FOR_SLUG_LOGIN = _(
    "The attempt to login with this organization name was not successful. Please try again, or contact our support."
)


class EnterpriseSelectionForm(forms.Form):
    """
    Enterprise Selection Form.
    """

    enterprise = forms.ChoiceField(
        choices=(),
        label='Organization',
        widget=forms.Select(
            attrs={'class': 'form-control', 'type': 'select'}
        ))
    success_url = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        """
        Initialize form.
        """
        super(EnterpriseSelectionForm, self).__init__(*args, **kwargs)
        initial = kwargs['initial']
        self._user_id = kwargs['initial'].pop('user_id')
        self.fields['enterprise'].choices = initial['enterprises']
        self.fields['success_url'].initial = initial['success_url']

    def clean(self):
        """
        Validate POST data.
        """
        cleaned_data = super(EnterpriseSelectionForm, self).clean()
        enterprise = cleaned_data.get('enterprise')

        try:
            EnterpriseCustomer.objects.get(uuid=enterprise)  # pylint: disable=no-member
        except EnterpriseCustomer.DoesNotExist:
            raise forms.ValidationError(_("Enterprise not found"))

        # verify that learner is really a member of selected enterprise
        if not EnterpriseCustomerUser.objects.filter(enterprise_customer=enterprise, user_id=self._user_id).exists():
            raise forms.ValidationError(_("Wrong Enterprise"))

        return cleaned_data


class EnterpriseLoginForm(forms.Form):
    """
    Enterprise Slug Login Form.
    """

    enterprise_slug = forms.CharField(
        label='Organization name',
        widget=forms.TextInput(
            attrs={'class': 'form-control'}
        )
    )

    def clean(self):
        """
        Validate POST data.
        """
        cleaned_data = super(EnterpriseLoginForm, self).clean()
        enterprise_slug = cleaned_data['enterprise_slug']

        # verify that given slug has any associated enterprise customer.
        try:
            enterprise_customer = EnterpriseCustomer.objects.get(slug=enterprise_slug)
        except EnterpriseCustomer.DoesNotExist:
            LOGGER.error("[Enterprise Slug Login] Not found enterprise: {}".format(enterprise_slug))
            raise forms.ValidationError(ERROR_MESSAGE_FOR_SLUG_LOGIN)

        # verify that enterprise customer has enabled the slug login feature.
        if not enterprise_customer.enable_slug_login:
            LOGGER.error("[Enterprise Slug Login] slug login not enabled for enterprise: {}".format(enterprise_slug))
            raise forms.ValidationError(ERROR_MESSAGE_FOR_SLUG_LOGIN)

        # verify that there are not multiple IDPs attached to the enterprise customer.
        enterprise_customer_idps = enterprise_customer.identity_providers
        if enterprise_customer_idps.count() > 1:
            LOGGER.error("[Enterprise Slug Login] Multiple IDPs configured for enterprise: {}".format(enterprise_slug))
            raise forms.ValidationError(ERROR_MESSAGE_FOR_SLUG_LOGIN)

        # verify that a valid idp is linked to the enterprise customer.
        enterprise_customer_idp = enterprise_customer_idps.first()
        if enterprise_customer_idp is None or enterprise_customer_idp.identity_provider is None:
            LOGGER.error("[Enterprise Slug Login] No IDP found or enterprise_customer linked to idp which is not in"
                         " the Registry class for enterprise: {}".format(enterprise_slug))
            raise forms.ValidationError(ERROR_MESSAGE_FOR_SLUG_LOGIN)

        cleaned_data['provider_id'] = enterprise_customer_idp.provider_id
        return cleaned_data
