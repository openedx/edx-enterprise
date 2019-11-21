# -*- coding: utf-8 -*-
"""
User-facing forms for the Enterprise app.
"""
from __future__ import absolute_import, unicode_literals

from django import forms
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser

ENTERPRISE_SELECT_SUBTITLE = _(
    u'You have access to multiple organizations. Select the organization that you will use '
    'to sign up for courses. If you want to change organizations, sign out and sign back in.'
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
