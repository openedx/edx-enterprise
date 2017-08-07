# -*- coding: utf-8 -*-
"""
Mixins for edX Enterprise's Consent application.
"""

from __future__ import absolute_import, unicode_literals

from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class ConsentModelMixin(object):
    """
    A mixin for Data Sharing Consent classes that require common, reusable functionality.
    """

    def __str__(self):
        """
        Return a human-readable string representation.
        """
        return "<{class_name} for user {username} of Enterprise {enterprise_name}>".format(
            class_name=self.__class__.__name__,
            username=self.username,
            enterprise_name=self.enterprise_customer.name,
        )

    def __repr__(self):
        """
        Return a uniquely identifying string representation.
        """
        return self.__str__()
