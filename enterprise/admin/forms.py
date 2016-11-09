# -*- coding: utf-8 -*-
"""
Custom admin forms.
"""
from __future__ import absolute_import, unicode_literals

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import ugettext as _

from enterprise import utils
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


class EnterpriseCustomerForm(forms.ModelForm):
    """
    A custom model form to convert a CharField to a TypedChoiceField.

    A model form that converts a CharField to a TypedChoiceField if the choices
    to display are accessible.
    """

    def __init__(self, *args, **kwargs):
        """
        Convert SlugField to TypedChoiceField if choices can be accessed.
        """
        super(EnterpriseCustomerForm, self).__init__(*args, **kwargs)
        idp_choices = utils.get_idp_choices()
        if idp_choices is not None:
            self.fields['identity_provider'] = forms.TypedChoiceField(choices=idp_choices, required=False)

    class Meta:
        model = EnterpriseCustomer
        fields = "__all__"
