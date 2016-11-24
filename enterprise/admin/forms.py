# -*- coding: utf-8 -*-
"""
Forms to be used in the enterprise djangoapp.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from django.utils.translation import ugettext as _

from enterprise import utils
from enterprise.course_catalog_api import get_all_catalogs
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerIdentityProvider, EnterpriseCustomerUser

logger = getLogger(__name__)  # pylint: disable=invalid-name


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


class EnterpriseCustomerIdentityProviderAdminForm(forms.ModelForm):
    """
    Alternate form for the EnterpriseCustomerIdentityProvider admin page.

    This form fetches identity providers from lms third_party_auth app.
    If third_party_auth app is not avilable it displays provider_id as a CharField.
    """
    class Meta:
        model = EnterpriseCustomerIdentityProvider
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        """
        Initialize the form.

        Substitutes CharField with TypedChoiceField for the provider_id field.
        """
        super(EnterpriseCustomerIdentityProviderAdminForm, self).__init__(*args, **kwargs)
        idp_choices = utils.get_idp_choices()
        if idp_choices is not None:
            self.fields['provider_id'] = forms.TypedChoiceField(choices=idp_choices)

    def clean(self):
        """
        Final validations of model fields.

        1. Validate that selected site for enterprise customer matches with the selected identity provider's site.
        """
        super(EnterpriseCustomerIdentityProviderAdminForm, self).clean()

        provider_id = self.cleaned_data.get('provider_id', None)
        enterprise_customer = self.cleaned_data.get('enterprise_customer', None)

        if provider_id is None or enterprise_customer is None:
            # field validation for either provider_id or enterprise_customer has already raised
            # a validation error.
            return
        try:
            identity_provider = utils.get_identity_provider(provider_id)
        except ObjectDoesNotExist:
            # This should not happen, as identity providers displayed in drop down are fetched dynamically.
            message = _(
                "Selected Identity Provider does not exist, please contact system administrator for more info.",
            )
            # Log message for debugging
            logger.exception(message)

            raise ValidationError(message)

        if identity_provider and identity_provider.site != enterprise_customer.site:
            raise ValidationError(
                _(
                    "Site ({identity_provider_site}) of selected identity provider does not match with "
                    "enterprise customer's site ({enterprise_customer_site})."
                    "Please either select site with domain '{identity_provider_site}' or update identity provider's "
                    "site to '{enterprise_customer_site}'."
                ).format(
                    enterprise_customer_site=enterprise_customer.site,
                    identity_provider_site=identity_provider.site,
                ),
            )
