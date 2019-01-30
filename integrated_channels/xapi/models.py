# -*- coding: utf-8 -*-

"""
Models for xAPI.
"""
from __future__ import absolute_import, unicode_literals

import base64

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from model_utils.models import TimeStampedModel

from enterprise.models import EnterpriseCustomer


@python_2_unicode_compatible
class XAPILRSConfiguration(TimeStampedModel):
    """
    xAPI LRS configurations.

    .. no_pii:
    """

    enterprise_customer = models.OneToOneField(
        EnterpriseCustomer,
        blank=False,
        null=False,
        help_text=_('Enterprise Customer associated with the configuration.'),
    )
    version = models.CharField(max_length=16, default='1.0.1', help_text=_('Version of xAPI.'))
    endpoint = models.URLField(help_text=_('URL of the LRS.'))
    key = models.CharField(max_length=255, verbose_name="Client ID", help_text=_('Key of xAPI LRS.'))
    secret = models.CharField(max_length=255, verbose_name="Client Secret", help_text=_('secret of xAPI LRS.'))
    active = models.BooleanField(
        blank=False,
        null=False,
        help_text=_('Is this configuration active?'),
    )

    class Meta:
        app_label = 'xapi'

    def __str__(self):
        """
        Return human-readable string representation.
        """
        return '<XAPILRSConfiguration for Enterprise {enterprise_name}>'.format(
            enterprise_name=self.enterprise_customer.name
        )

    def __repr__(self):
        """
        Return uniquely identifying string representation.
        """
        return self.__str__()

    @property
    def authorization_header(self):
        """
        Authorization header for authenticating requests to LRS.
        """
        return 'Basic {}'.format(
            base64.b64encode('{key}:{secret}'.format(key=self.key, secret=self.secret).encode()).decode()
        )
