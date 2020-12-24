# -*- coding: utf-8 -*-
"""
Django admin integration for configuring moodle app to communicate with Moodle systems.
"""

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from integrated_channels.moodle.models import MoodleEnterpriseCustomerConfiguration


class MoodleEnterpriseCustomerConfigurationForm(forms.ModelForm):
    """
    Django admin form for MoodleEnterpriseCustomerConfiguration.
    """
    class Meta:
        model = MoodleEnterpriseCustomerConfiguration
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        cleaned_username = cleaned_data.get('username')
        cleaned_password = cleaned_data.get('password')
        cleaned_token = cleaned_data.get('token')
        if cleaned_token and (cleaned_username or cleaned_password):
            raise ValidationError(_('Cannot set both a Username/Password and Token'))
        if (cleaned_username and not cleaned_password) or (cleaned_password and not cleaned_username):
            raise ValidationError(_('Must set both a Username and Password, not just one'))


@admin.register(MoodleEnterpriseCustomerConfiguration)
class MoodleEnterpriseCustomerConfigurationAdmin(admin.ModelAdmin):
    """
    Django admin model for MoodleEnterpriseCustomerConfiguration.
    """

    form = MoodleEnterpriseCustomerConfigurationForm
