# -*- coding: utf-8 -*-
"""
User-facing forms for the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from django import forms
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser
from enterprise.utils import get_enterprise_customer_idp

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

    enterprise = forms.ChoiceField(choices=(), label='Organization')
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

    enterprise_slug = forms.CharField(label='Company Name')

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
            raise forms.ValidationError(ERROR_MESSAGE_FOR_SLUG_LOGIN)

        # verify that enterprise customer has enabled the slug login feature.
        if not enterprise_customer.enable_slug_login:
            raise forms.ValidationError(ERROR_MESSAGE_FOR_SLUG_LOGIN)

        # verify that a valid idp is linked to the enterprise customer.
        enterprise_customer_idp = get_enterprise_customer_idp(enterprise_slug)
        if enterprise_customer_idp is None or enterprise_customer_idp.identity_provider is None:
            raise forms.ValidationError(ERROR_MESSAGE_FOR_SLUG_LOGIN)
        return cleaned_data
