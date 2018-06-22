# -*- coding: utf-8 -*-
from django.core.paginator import Paginator


class CustomPaginator(Paginator):
    """
    Adopted from django/core/paginator so as to implement smart links pagination in custom views.
    """
    _page_range = []

    @property
    def page_range(self):
        return self._page_range or list(range(1, self.num_pages + 1))

    @page_range.setter
    def page_range(self, value):
        self._page_range = value
