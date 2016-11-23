# -*- coding: utf-8 -*-
"""
Forms to be used in the enterprise djangoapp.
"""
from __future__ import absolute_import, unicode_literals

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import ugettext as _

from enterprise import utils
from enterprise.course_catalog_api import get_all_catalogs
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser


class ManageLearnersForm(forms.Form):
    """
    Form to manage learner additions.
    """
    email = forms.CharField(label=_("Email or Username"))

    def clean_email(self):
        """
        Clean email form field

        Returns:
            str: email to link
        """
        email_or_username = self.cleaned_data["email"].strip()
        try:
            user = User.objects.get(username=email_or_username)
            email = user.email
        except User.DoesNotExist:
            email = email_or_username

        try:
            validate_email(email)
        except ValidationError:
            message = _("{email_or_username} does not appear to be a valid email or known username").format(
                email_or_username=email_or_username
            )
            raise ValidationError(message)

        existing_record = EnterpriseCustomerUser.objects.get_link_by_email(email)
        if existing_record:
            message = _("User with email {email} is already registered with Enterprise Customer {ec_name}").format(
                email=email, ec_name=existing_record.enterprise_customer.name
            )
            raise ValidationError(message)

        return email


class EnterpriseCustomerAdminForm(forms.ModelForm):
    """
    Alternate form for the EnterpriseCustomer admin page.

    This form fetches catalog names and IDs from the course catalog API.
    """
    class Meta:
        model = EnterpriseCustomer
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        """
        Initialize the form.

        Substitute a ChoiceField in for the catalog field that would
        normally be set up as a plain number entry field.
        """
        super(EnterpriseCustomerAdminForm, self).__init__(*args, **kwargs)
        self.fields['catalog'] = forms.ChoiceField(choices=self.get_catalog_options())
        idp_choices = utils.get_idp_choices()
        if idp_choices is not None:
            self.fields['identity_provider'] = forms.TypedChoiceField(choices=idp_choices, required=False)

    def get_catalog_options(self):
        """
        Retrieve a list of catalog ID and name pairs.

        Once retrieved, these name pairs can be used directly as a value
        for the `choices` argument to a ChoiceField.
        """
        return ((None, _('None'),),) + tuple(
            (catalog['id'], catalog['name'],)
            for catalog in get_all_catalogs(self.user)
        )
