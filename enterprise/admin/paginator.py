# -*- coding: utf-8 -*-
"""
Custom paginator to implement smart pagination.
"""
from __future__ import absolute_import, unicode_literals

from django.core.paginator import Paginator


class CustomPaginator(Paginator):
    """
    Adopted from django/core/paginator
    so as to implement smart links pagination in custom views.
    """
    _page_range = []

    @property
    def page_range(self):
        """
        We have customized the getter so that it can return the value of the page_range property
        instead of always calculating the result.
        """
        return self._page_range or list(range(1, self.num_pages + 1))

    @page_range.setter
    def page_range(self, value):
        """
        We have introduced a setter method here, so as to set value for page_range property.
        This was not present in Paginator class.
        """
        self._page_range = value
